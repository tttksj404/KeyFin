package com.finset.key_fin.item.entity;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ItemTest {

	@Test
	void defaultsToActive() {
		Item item = new Item();

		assertThat(item.isActive()).isTrue();
	}
}
