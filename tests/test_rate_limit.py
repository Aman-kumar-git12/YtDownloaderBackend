from core import rate_limit
from core.rate_limit import RateLimiter


def test_blocks_after_limit_and_recovers(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])
    limiter = RateLimiter(limit=2, window_seconds=60)

    assert limiter.check("1.2.3.4") == 0
    assert limiter.check("1.2.3.4") == 0
    assert limiter.check("1.2.3.4") == 60
    assert limiter.check("5.6.7.8") == 0  # other clients unaffected

    now[0] += 60
    assert limiter.check("1.2.3.4") == 0
