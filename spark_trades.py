from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, avg, sum, count, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType

# 1. Initialize Spark Session
# We need to add the Elastic and Kafka packages
spark = SparkSession.builder \
    .appName("CryptoTradesAnalytics") \
    .config("spark.es.nodes", "elasticsearch") \
    .config("spark.es.port", "9200") \
    .config("spark.es.nodes.wan.only", "true") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# 2. Define Schema
schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("price", StringType(), True),   # Incoming as string, we cast later
    StructField("volume", StringType(), True),  # Incoming as string
    StructField("timestamp", StringType(), True),
    StructField("source", StringType(), True)
])

# 3. Read from Kafka (financial_trades)
df_kafka = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "financial_trades") \
    .option("startingOffsets", "latest") \
    .load()

# 4. Parse & Type Cast
# We divide timestamp by 1000 because Spark expects seconds for casting to TimestampType, 
# but APIs often send milliseconds.
df_parsed = df_kafka.select(
    from_json(col("value").cast("string"), schema).alias("data")
).select(
    col("data.symbol"),
    col("data.source"),
    col("data.price").cast(DoubleType()).alias("price"),
    col("data.volume").cast(DoubleType()).alias("volume"),
    (col("data.timestamp") / 1000).cast("timestamp").alias("event_time")
)

# 5. Core Logic: Windowed Aggregation
# Calculate stats every 10 seconds for the last 1 minute window
df_analytics = df_parsed \
    .withWatermark("event_time", "1 minute") \
    .groupBy(
        window(col("event_time"), "1 minute", "10 seconds"),
        col("symbol"),
        col("source")
    ) \
    .agg(
        avg("price").alias("avg_price"),
        sum("volume").alias("total_volume"),
        count("*").alias("trade_count")
    ) \
    .select(
        col("window.start").alias("window_start"),
        col("window.end").alias("window_end"),
        col("symbol"),
        col("source"),
        col("avg_price"),
        col("total_volume"),
        col("trade_count"),
        current_timestamp().alias("processing_time")
    )

# 6. Write to Elasticsearch
query = df_analytics.writeStream \
    .format("org.elasticsearch.spark.sql") \
    .outputMode("append") \
    .option("checkpointLocation", "/tmp/checkpoints/trades") \
    .option("es.resource", "market_prices") \
    .start()

query.awaitTermination()