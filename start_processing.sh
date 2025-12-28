#!/bin/bash

# Define the packages (Exact versions for Spark 3.4 + Elastic 8.11)
PACKAGES="org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.2,org.elasticsearch:elasticsearch-spark-30_2.12:8.11.1"

echo "🚀 Submitting TRADES Job..."
docker exec -d spark-master /opt/spark/bin/spark-submit \
  --conf "spark.jars.ivy=/tmp/.ivy2" \
  --packages "$PACKAGES" \
  --master spark://spark-master:7077 \
  /opt/spark/apps/spark_trades.py

# echo "📰 Submitting NEWS Job..."
# docker exec -d spark-master /opt/spark/bin/spark-submit \
#   --conf "spark.jars.ivy=/tmp/.ivy2" \
#   --packages "$PACKAGES" \
#   --master spark://spark-master:7077 \
#   /opt/spark/apps/spark_news.py

echo "✅ Jobs submitted in background."
echo "Monitor logs with: docker logs spark-master -f"