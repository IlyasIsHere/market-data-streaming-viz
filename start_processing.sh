#!/bin/bash

# Define the packages (Exact versions for Spark 3.4 + Elastic 8.11)
PACKAGES="org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.2,org.elasticsearch:elasticsearch-spark-30_2.12:8.11.1"

# Create Elasticsearch index templates with correct date mappings
echo "📋 Creating Elasticsearch index templates..."
curl -X PUT "http://localhost:9200/_index_template/market_prices_template" -H "Content-Type: application/json" -d '{
  "index_patterns": ["market_prices*"],
  "priority": 500,
  "template": {
    "mappings": {
      "properties": {
        "window_start": {"type": "date", "format": "epoch_millis"},
        "window_end": {"type": "date", "format": "epoch_millis"},
        "processing_time": {"type": "date", "format": "epoch_millis"},
        "symbol": {"type": "keyword"},
        "source": {"type": "keyword"},
        "avg_price": {"type": "double"},
        "total_volume": {"type": "double"},
        "trade_count": {"type": "long"}
      }
    }
  }
}' > /dev/null 2>&1

curl -X PUT "http://localhost:9200/_index_template/news_sentiment_template" -H "Content-Type: application/json" -d '{
  "index_patterns": ["news_sentiment*"],
  "priority": 500,
  "template": {
    "mappings": {
      "properties": {
        "news_timestamp": {"type": "date", "format": "epoch_second"},
        "processing_time": {"type": "date"},
        "headline": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        "summary": {"type": "text"},
        "article_url": {"type": "keyword"},
        "sentiment_score": {"type": "float"},
        "sentiment": {"type": "keyword"}
      }
    }
  }
}' > /dev/null 2>&1

echo "✅ Index templates created."

echo "🚀 Submitting TRADES Job (limited to 1 core)..."
docker exec -d spark-master /opt/spark/bin/spark-submit \
  --conf "spark.jars.ivy=/tmp/.ivy2" \
  --conf "spark.cores.max=1" \
  --packages "$PACKAGES" \
  --master spark://spark-master:7077 \
  /opt/spark/apps/spark_trades.py

# Wait a few seconds before starting the second job
sleep 3

echo "📰 Submitting NEWS Job (limited to 1 core)..."
docker exec -d spark-master /opt/spark/bin/spark-submit \
  --conf "spark.jars.ivy=/tmp/.ivy2" \
  --conf "spark.cores.max=1" \
  --packages "$PACKAGES" \
  --master spark://spark-master:7077 \
  /opt/spark/apps/spark_news.py

echo "✅ Jobs submitted in background."
echo ""
echo "📊 Monitor with:"
echo "  - Spark UI: http://localhost:8080"
echo "  - Spark logs: docker logs spark-master -f"
echo "  - Check data: curl http://localhost:9200/market_prices/_count && curl http://localhost:9200/news_sentiment/_count"