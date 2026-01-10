from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, udf, current_timestamp, when
from pyspark.sql.types import StructType, StructField, StringType, LongType, FloatType

# 1. Initialize Spark Session
spark = SparkSession.builder \
    .appName("NewsAnalytics") \
    .config("spark.es.nodes", "elasticsearch") \
    .config("spark.es.port", "9200") \
    .config("spark.es.nodes.wan.only", "true") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# 2. TextBlob Sentiment Analysis
def analyze_sentiment_textblob(text):
    """
    TextBlob sentiment analysis using pre-trained Naive Bayes classifier.
    Returns: sentiment score between -1 (very negative) and 1 (very positive)
    """
    if not text or text.strip() == "":
        return 0.0

    try:
        from textblob import TextBlob

        # Create TextBlob object
        blob = TextBlob(text)

        # Get polarity score (-1 to 1)
        # TextBlob returns: -1 (most negative) to 1 (most positive)
        sentiment_score = blob.sentiment.polarity

        return float(sentiment_score)
    except Exception as e:
        # If any error, return neutral
        return 0.0

def categorize_sentiment(score):
    """Convert sentiment score to category"""
    if score >= 0.15:
        return "positive"
    elif score <= -0.15:
        return "negative"
    else:
        return "neutral"

# Register UDFs
sentiment_score_udf = udf(analyze_sentiment_textblob, FloatType())
sentiment_category_udf = udf(categorize_sentiment, StringType())

# 3. Define Schema for incoming news
schema = StructType([
    StructField("headline", StringType(), True),
    StructField("summary", StringType(), True),
    StructField("article_url", StringType(), True),
    StructField("timestamp", StringType(), True)
])

# 4. Read from Kafka (financial_news)
df_kafka = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "financial_news") \
    .option("startingOffsets", "earliest") \
    .option("failOnDataLoss", "false") \
    .option("maxOffsetsPerTrigger", "1000") \
    .load()

# 5. Parse JSON and process
df_parsed = df_kafka.select(
    from_json(col("value").cast("string"), schema).alias("data")
).select(
    col("data.headline"),
    col("data.summary"),
    col("data.article_url"),
    col("data.timestamp").cast(LongType()).alias("news_timestamp")
)

# 6. Add sentiment analysis
df_with_sentiment = df_parsed \
    .withColumn("combined_text",
                when(col("summary").isNotNull(), col("summary"))
                .otherwise(col("headline"))) \
    .withColumn("sentiment_score", sentiment_score_udf(col("combined_text"))) \
    .withColumn("sentiment", sentiment_category_udf(col("sentiment_score"))) \
    .withColumn("processing_time", current_timestamp()) \
    .select(
        col("headline"),
        col("summary"),
        col("article_url"),
        col("news_timestamp"),
        col("sentiment_score"),
        col("sentiment"),
        col("processing_time")
    )

# 7. Write to Elasticsearch
query = df_with_sentiment.writeStream \
    .format("org.elasticsearch.spark.sql") \
    .outputMode("append") \
    .option("checkpointLocation", "/tmp/checkpoints/news") \
    .option("es.resource", "news_sentiment") \
    .option("es.batch.size.entries", "100") \
    .option("es.batch.size.bytes", "1mb") \
    .option("es.batch.write.refresh", "false") \
    .trigger(processingTime="10 seconds") \
    .start()

print("NewsAnalytics job started successfully")
print("Waiting for streaming data from financial_news topic...")
query.awaitTermination()
