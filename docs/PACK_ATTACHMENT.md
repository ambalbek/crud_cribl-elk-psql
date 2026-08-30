# Pack Attachment Point — Discovery

## Sources inspection

`cribl-edge/local/cribl/inputs.yml` defines two sources:

- `in_open_telemetry` — OpenTelemetry receiver on port 4317
- `http` — HTTP API on port 10080 (Cribl, Splunk HEC, Elastic APIs)

Both sources have `sendToRoutes: false` and connect directly to outputs
(`es_direct`, `logstash_traces`). Multiple data types (Mulesoft, ForgeRock,
Spring Boot, etc.) arrive on the **same** sources.

## Conclusion

**Sources are shared** — multiple data types share the same Cribl Source.

Therefore: attach packs at the **route** level, filtered by data type.

This means:
- Each onboarded application gets a route entry
- The route references the resolved pack as its pipeline
- No `sources.py` router is needed in `cribl_service`
- The pack processes events inline as part of the route's pipeline chain

## Why not source-level

Source-level pre-processing would apply the pack to **all** events arriving on
that source, regardless of data type. Since multiple data types share a source,
this would apply the wrong pack to the wrong events.

## Why not destination-level

Destination post-processing runs after routing decisions. By that point the
events have already been routed, but the pack needs to run during routing to
classify and transform before the destination writes to storage.
