# Scrapy settings for lm30 project

BOT_NAME = "lm30"

SPIDER_MODULES = ["lm30.spiders"]
NEWSPIDER_MODULE = "lm30.spiders"

SPIDER_CONTRACTS = {
    "lm30.contracts.FilersFormContract": 10,
    "lm30.contracts.FilingsFormContract": 11,
}

# Crawl responsibly by identifying yourself (and your website) on the user-agent
from olms import USER_AGENT  # noqa: E402, F401

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    "olms.middleware.BlockingBackoffMiddleware": 560,
}

# Set settings whose default value is deprecated to a future-proof value
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

# DOL's WAF (AWS ELB) 403s above a few req/s sustained; AutoThrottle adapts to
# the server's latency to stay under the limit, and
# BlockingBackoffMiddleware handles any 403/429 that still gets through
# (exponential slot backoff + retry, abort when persistently blocked).
# 403 is deliberately NOT in RETRY_HTTP_CODES: the stock RetryMiddleware
# retries immediately with no backoff, which just re-spends the request
# against the rate limiter.
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 60.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0
CONCURRENT_REQUESTS_PER_DOMAIN = 4

# Cache responses so the incremental spiders of one update run can
# share the slow filer detail responses. The shared storage class
# de-namespaces the cache (stock scrapy keys it by spider name); error
# responses are not cached, so a 403 can't satisfy its own retry.
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600
HTTPCACHE_DIR = ".scrapy/httpcache"
HTTPCACHE_STORAGE = "olms.cache.SharedFilesystemCacheStorage"
HTTPCACHE_IGNORE_HTTP_CODES = [400, 403, 404, 429, 500, 502, 503, 504]
