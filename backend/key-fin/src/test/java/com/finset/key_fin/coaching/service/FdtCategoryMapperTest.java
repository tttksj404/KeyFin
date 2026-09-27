package com.finset.key_fin.coaching.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

import com.finset.key_fin.coaching.service.FdtCategoryMapper.Entry;

class FdtCategoryMapperTest {

	private final FdtCategoryMapper mapper = new FdtCategoryMapper();

	/** 엔진이 category 로 봉투를 정할 때 쓰는 표. 우리 봉투 이름을 보내면 전부 기타로 떨어진다. */
	private static final Map<String, String> ENGINE_CATEGORY_ENVELOPE = Map.ofEntries(
			Map.entry("식비", "외식"),
			Map.entry("교통", "교통비"),
			Map.entry("건강", "의료·건강"),
			Map.entry("여가·문화", "취미·여가"),
			Map.entry("쇼핑", "쇼핑"),
			Map.entry("생활서비스", "쇼핑"),
			Map.entry("교육", "기타"),
			Map.entry("사회·경조", "기타"),
			Map.entry("주거·통신", "기타"),
			Map.entry("세금·공과", "기타"),
			Map.entry("보험", "기타"),
			Map.entry("업무", "기타")
	);

	/** 엔진이 subcategory 이름만으로 봉투를 확정하는 원시 라벨. 여기 걸리면 category 는 보지 않는다. */
	private static final Map<String, String> ENGINE_SUBCATEGORY_ENVELOPE = Map.ofEntries(
			Map.entry("카페", "외식"),
			Map.entry("배달", "외식"),
			Map.entry("주점", "외식"),
			Map.entry("대중교통", "교통비"),
			Map.entry("택시", "교통비"),
			Map.entry("주유", "교통비"),
			Map.entry("스포츠 관람", "취미·여가"),
			Map.entry("편의점", "편의점·마트·잡화"),
			Map.entry("장보기", "편의점·마트·잡화"),
			Map.entry("생활용품", "편의점·마트·잡화"),
			Map.entry("해외 결제", "기타")
	);

	static List<Object[]> 세분류와_기대_봉투() {
		return List.of(
				new Object[] {101, "외식"}, new Object[] {102, "외식"},
				new Object[] {103, "외식"}, new Object[] {104, "외식"},
				new Object[] {201, "교통비"}, new Object[] {202, "교통비"}, new Object[] {203, "교통비"},
				new Object[] {301, "의료·건강"}, new Object[] {302, "의료·건강"},
				new Object[] {401, "취미·여가"}, new Object[] {402, "취미·여가"},
				new Object[] {403, "취미·여가"}, new Object[] {404, "취미·여가"},
				new Object[] {501, "쇼핑"}, new Object[] {502, "쇼핑"}, new Object[] {503, "쇼핑"},
				new Object[] {601, "편의점·마트·잡화"}, new Object[] {602, "편의점·마트·잡화"},
				new Object[] {603, "편의점·마트·잡화"},
				new Object[] {701, "기타"}, new Object[] {702, "기타"}, new Object[] {703, "기타"}
		);
	}

	@ParameterizedTest(name = "세분류 {0} → 봉투 {1}")
	@MethodSource("세분류와_기대_봉투")
	void 세분류_22종이_의도한_봉투로_분류된다(int subcategoryId, String expectedEnvelope) {
		Entry entry = mapper.of(subcategoryId);

		assertThat(resolveEnvelope(entry)).isEqualTo(expectedEnvelope);
	}

	@Test
	void 마트는_원시_라벨_장보기로_보낸다() {
		Entry entry = mapper.of(602);

		assertThat(entry.subcategory()).isEqualTo("장보기");
		assertThat(ENGINE_CATEGORY_ENVELOPE.get(entry.category())).isEqualTo("쇼핑");
		assertThat(resolveEnvelope(entry)).isEqualTo("편의점·마트·잡화");
	}

	@Test
	void 세분류가_없으면_빈_문자열을_보낸다() {
		assertThat(mapper.of(null)).isEqualTo(new Entry("", ""));
		assertThat(mapper.of(999)).isEqualTo(new Entry("", ""));
	}

	@Test
	void category는_엔진_어휘만_사용한다() {
		for (Object[] row : 세분류와_기대_봉투()) {
			Entry entry = mapper.of((int) row[0]);
			assertThat(ENGINE_CATEGORY_ENVELOPE).containsKey(entry.category());
		}
	}

	/** 엔진의 판정 순서를 그대로 흉내 낸다 — subcategory 우선, 없으면 category 로 fallback. */
	private String resolveEnvelope(Entry entry) {
		String exact = ENGINE_SUBCATEGORY_ENVELOPE.get(entry.subcategory());
		return exact != null ? exact : ENGINE_CATEGORY_ENVELOPE.get(entry.category());
	}
}
