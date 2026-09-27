package com.finset.key_fin.support;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.util.concurrent.atomic.AtomicReference;

/** 통합 테스트가 공유하는 시계. 시각은 공유하고 zone 은 withZone 으로 갈라진다. */
public final class TestClock extends Clock {

	private final AtomicReference<Instant> instant;
	private final ZoneId zone;

	public TestClock(Instant instant, ZoneId zone) {
		this(new AtomicReference<>(instant), zone);
	}

	private TestClock(AtomicReference<Instant> instant, ZoneId zone) {
		this.instant = instant;
		this.zone = zone;
	}

	public void set(Instant value) {
		instant.set(value);
	}

	@Override
	public ZoneId getZone() {
		return zone;
	}

	@Override
	public Clock withZone(ZoneId zone) {
		return new TestClock(instant, zone);
	}

	@Override
	public Instant instant() {
		return instant.get();
	}
}
