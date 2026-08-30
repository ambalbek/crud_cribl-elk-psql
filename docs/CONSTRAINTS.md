# Constraints

## Partition cardinality and open-file limits

Cribl Stream imposes a per-Worker-Process open-file limit on each destination.
Every unique partition path produces one open file handle. The limit is
configurable via `maxOpenFiles` (default 100 per destination).

### What this means

- **One destination per application** is safe — partition cardinality is bounded
  by the number of log types (RIM, TRANS, BIZ, LGLHLD, UNCLASSIFIED) times
  date granularity. At daily granularity with 5 log types, that is ~5 open
  files per day per app.

- **A shared destination across all applications is NOT safe.** If 200 apps
  each produce 5 log types, that is 1,000 concurrent partition paths on a
  single destination — 10x the default limit. Events will be dropped or
  blocked depending on the `onBackpressure` setting.

### Do not consolidate destinations

Every previous design review has considered merging per-app destinations into
a shared one to reduce configuration. This is the reason it cannot be done.
The partition expression

```
`${apmid}/${__logType || 'UNCLASSIFIED'}/${C.Time.strftime(_time,'%Y/%m/%d')}`
```

produces a unique path per (app, log-type, day). With one destination per app
the cardinality stays within limits. With a shared destination it does not.

## LGLHLD requires a separate container

Azure Blob Storage immutability policies (legal hold, time-based retention)
are applied at **container scope**. A container with an immutability policy
cannot have objects deleted by lifecycle rules.

Since non-LGLHLD log types (RIM, TRANS, BIZ) are subject to retention-based
deletion, they cannot share a container with LGLHLD data. Therefore:

- Each app gets one standard destination + container for RIM/TRANS/BIZ
- LGLHLD compiles to a **separate destination and container** with the
  immutability policy applied at the container level

## Blob containers are manual

Containers are created by the storage team and verified by the framework with
a write-and-delete probe. The `createContainer` option on every Cribl Azure
Blob destination is explicitly set to `false`. The framework never creates
containers.
