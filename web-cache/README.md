# Native file cache and revalidation queue

`web_cache_new(directory)`, read/write/invalidate implement bounded entries with
TTL, hashed keys, atomic rename and fsync. Capture `web_cache_tagged_key` before
rendering; tag invalidation changes the generation, preventing an in-flight old
render from being published under the new generation.

## Disk bound

Entries live in a fixed set of slot files, `slot-0` to `slot-N`, chosen by the
key's SHA-256. Each file stores the expiry, the key's hash and the value, so a
read of a key whose slot now holds another key is a miss. `web_cache_new` uses
4,096 slots and values up to 8 MiB; `web_cache_new_bounded(directory, slots,
max_value)` picks both (1–1,048,576 slots, 1 byte–8 MiB values). The directory
then holds at most `slots` entries, so at most about `slots × max_value` bytes,
plus one small `tag-…` file per tag name and the revalidation queue. Keep tag
names to a fixed set; tag files are not evicted, because evicting one would
bring back an old generation.

`web_cache_sweep(cache, now)` removes expired entries, reading only each slot's
first line, and returns how many it removed. Run it periodically, for example
from the revalidation worker. A slot rewritten between the check and the removal
is lost as well; that is a cache miss, never stale data. Reads of an expired
entry miss without deleting it.

Caches written before this layout used 43-character file names. Nothing reads
them any more; delete them, or empty the directory, when upgrading.

## Revalidation queue

The native queue serializes enqueue/dequeue with flock, bounds its file to 1 MiB
and uses short-lived pending markers for duplicate suppression. A consumer
validates its fixed origin and authentication secret before fetching queued
paths. Dequeue drains a batch; a worker crash can lose that batch. Hard TTL
expiry remains the freshness fallback. There is no distributed coordination or
durable job acknowledgement. NeoKit supplies the native worker and HTTP
integration tests; `tests/web_foundations.neo` covers eviction, the size limit,
the sweep and tags.
