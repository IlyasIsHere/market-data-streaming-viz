# Market Data Streaming and Visualization

A simple trades/news visualization app using:
- Apache NiFi for data ingestion from Binance and FinnHub APIs 
- Apache Kafka for message queuing
- Spark Streaming for analytics and processing
- Elasticsearch for storage 
- Kibana for visualization

![alt text](image-23.png)

----

# Quick Start

## Starting the Services
1. **Clone the Repository**
    ```bash
    git clone https://github.com/ilyasishere/market-data-streaming-viz.git
    cd market-data-streaming-viz
    ```
2. **Start Docker Containers**
    ```bash
    docker compose up -d
    ```
3. **Access the Services**
    - NiFi: `https://localhost:8080/nifi` 
        - (login with `admin` / `password12345678`)
        - Make sure to use `https` protocol, as it won't work with `http`.
    - NiFi Registry: `http://localhost:18080/nifi-registry`
    - Kibana: `http://localhost:5601`


## Importing the NiFi Workflow

1. **Set Up NiFi Registry Client**
    - In NiFi, create a new `NifiRegistryFlowRegistryClient` under Controller Services.

    ![alt text](image.png)
    ![alt text](image-1.png)
    - Set the URL to `http://nifi-registry:18080`.

    ![alt text](image-2.png)


2. **Create a Bucket in NiFi Registry**
    - Open the Registry UI at `http://localhost:18080/nifi-registry`.
    - Go to Settings on the top right.
    - Create a bucket named `main-flows`.

    ![alt text](image-3.png)


3. **Import the Workflow**
    - On the Registry homepage, click **Import New Flow**.
    - Set the flow name to `main`.
    - Select the `main-flows` bucket.
    - Upload the `workflow.json` file as the Flow Definition.
    - Click **Import**.

    ![alt text](image-4.png)

4. **Deploy the Workflow in NiFi**
    - In the NiFi UI, drag the **Import from Registry** icon onto the canvas.

    ![alt text](image-5.png)
    - Select the `main-flows` bucket and the `main` flow.
    - Click **Import**.

    ![alt text](image-6.png)

5. **Enable and Start the Workflow**
    - Right-click the `main` process group you just imported.
    - Click **Enable all controller services**.

    ![alt text](image-7.png)

    - Right-click again and select **Start** to run the workflow.

    ![alt text](image-8.png)


## Launching the Spark Streaming jobs

It's as easy as running the `start_processing.sh` script:

On Linux/Mac:
```bash
./start_processing.sh
``` 
On Windows:
```bash
bash ./start_processing.sh
```

## Visualizing Data in Kibana
TODO


----
# How It Works
## 1. Data Ingestion with NiFi 

NiFi fetches real-time trade data from Binance and news data from FinnHub APIs, then pushes this data into Kafka topics.

The image below shows the whole NiFi workflow. The workflow on the right is responsible for fetching trade data using websockets, while the left side handles news data fetching via REST API calls.

![alt text](Untitled.png)

### Trades data

For the ConnectWebSocket processor to work, we need to create a Jetty WebSocketClient Service. We then configure the WebSocket URI property to point to the FinnHub trades stream endpoint, with the API key:

![alt text](image-10.png)

The left-most path sends a subscription message to the FinnHub API to start receiving trades data for the symbols we specified.

![alt text](image-9.png)

The path next to it receives the incoming trades data, splits the JSON array into individual messages (because FinnHub sends trades in batches), then renames the attributes (e.g. changing "p" to "price") for better readability. Finally, the output is converted back into a json and is published to the Kafka topic `financial_trades`, using the PublishKafka NiFi processor and a Kafka3ConnectionService.

![alt text](image-11.png)
![alt text](image-12.png)

![alt text](image-13.png)
*Kafka3ConnectionService configuration*

![alt text](image-14.png)
*PublishKafka processor configuration: we use the trade `symbol` as the Kafka Key*


![alt text](image-15.png)  
*PublishKafka processor configuration: setting `financial_trades` as the Kafka Topic*

**Note:**
The same thing goes for the Binance API, except that it uses a different WebSocket endpoint and different message format.


### News data

The news data ingestion flow is simpler, as it uses REST API calls every 60 seconds instead of websockets.

![alt text](image-16.png)

We use the InvokeHTTP NiFi processor to call the FinnHub news endpoint, setting the API key and other parameters in the URL:

![alt text](image-17.png)

We set the scheduler to run every 1 minute:

![alt text](image-18.png)

Then, the SplitJson processor splits the returned JSON array of news articles into individual messages, using the JsonPath expression `$`:

![alt text](image-19.png)

After that, we rename some attributes (e.g. url to article_url):

![alt text](image-20.png)

Then, we set the schema and convert the data back to JSON format using the AttributesToJson processor:

![alt text](image-21.png)

Finally, we publish the news data to the Kafka topic `financial_news` using the PublishKafka processor:

![alt text](image-22.png)


## 2. Data Processing with Spark Streaming