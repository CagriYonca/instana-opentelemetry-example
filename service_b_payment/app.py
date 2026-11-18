import os
import time
import uuid
from flask import Flask, request, jsonify
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.flask import FlaskInstrumentor

provider = TracerProvider(
    resource=Resource.create(
        {SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "payment-service")}
    )
)
provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://instana-agent:4317"),
            insecure=True,
        )
    )
)
trace.set_tracer_provider(provider)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)   # this line reads `traceparent` for us

@app.route("/api/v1/payments", methods=["POST"])
def process_payment():
    data = request.get_json() or {}
    span = trace.get_current_span()
    span.set_attribute("payment.order_id", data.get("order_id", ""))
    span.set_attribute("payment.amount", data.get("amount", 0.0))
    span.set_attribute("payment.gateway", "MockGateway")

    time.sleep(0.08)  # pretend to talk to a payment gateway

    transaction_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    span.set_attribute("payment.transaction_id", transaction_id)
    span.set_attribute("payment.status", "authorized")

    # echo the header we received, so we can compare it later
    return jsonify({
        "status": "authorized",
        "transaction_id": transaction_id,
        "traceparent_received": request.headers.get("traceparent"),
    }), 200
