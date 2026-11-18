import os
import httpx
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

provider = TracerProvider(
    resource=Resource.create(
        {SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "order-service")}
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
tracer = trace.get_tracer(__name__)

app = FastAPI()
FastAPIInstrumentor.instrument_app(app)   # traces every incoming request

PAYMENT_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:5001")

@app.post("/api/v1/orders")
async def create_order(payload: dict):
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("order.id", payload.get("order_id", ""))
        span.set_attribute("order.amount", payload.get("amount", 0.0))

        headers: dict = {}
        TraceContextTextMapPropagator().inject(headers)   # writes `traceparent`

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{PAYMENT_URL}/api/v1/payments", json=payload, headers=headers
            )

        # echo the header we sent, so we can compare it later
        return {
            "order_id": payload.get("order_id"),
            "traceparent_sent": headers.get("traceparent"),
            "payment": resp.json(),
        }
