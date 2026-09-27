package com.finset.key_fin.coaching.service;

import java.util.Map;

import org.springframework.stereotype.Component;

/**
 * 세분류 ID를 FDT 엔진이 요구하는 category·subcategory 문자열로 바꾼다.
 *
 * <p>엔진은 subcategory 를 자체 원시 라벨 사전에서 먼저 찾고, 없으면 category 로 봉투를 정한다.
 * 그래서 category 에는 봉투 이름이 아니라 엔진 어휘(식비·교통·건강·여가·문화·쇼핑·생활서비스·기타)를 넣는다.
 */
@Component
public class FdtCategoryMapper {

	/** 엔진의 CATEGORY_ENVELOPE['생활서비스'] 가 쇼핑이라, 마트는 원시 라벨 '장보기' 로 보내야 봉투가 맞는다. */
	private static final String MART_RAW_LABEL = "장보기";

	private static final Map<Integer, Entry> BY_SUBCATEGORY = Map.ofEntries(
			Map.entry(101, new Entry("식비", "음식점")),
			Map.entry(102, new Entry("식비", "카페")),
			Map.entry(103, new Entry("식비", "배달")),
			Map.entry(104, new Entry("식비", "주점")),
			Map.entry(201, new Entry("교통", "대중교통")),
			Map.entry(202, new Entry("교통", "택시")),
			Map.entry(203, new Entry("교통", "주유")),
			Map.entry(301, new Entry("건강", "병원·약국")),
			Map.entry(302, new Entry("건강", "운동·헬스")),
			Map.entry(401, new Entry("여가·문화", "영화·공연·전시")),
			Map.entry(402, new Entry("여가·문화", "스포츠 관람")),
			Map.entry(403, new Entry("여가·문화", "게임·콘텐츠")),
			Map.entry(404, new Entry("여가·문화", "여행·숙박")),
			Map.entry(501, new Entry("쇼핑", "패션·잡화")),
			Map.entry(502, new Entry("쇼핑", "뷰티")),
			Map.entry(503, new Entry("쇼핑", "온라인 쇼핑")),
			Map.entry(601, new Entry("생활서비스", "편의점")),
			Map.entry(602, new Entry("생활서비스", MART_RAW_LABEL)),
			Map.entry(603, new Entry("생활서비스", "생활용품")),
			Map.entry(701, new Entry("교육", "교육")),
			Map.entry(702, new Entry("사회·경조", "해외 결제")),
			Map.entry(703, new Entry("사회·경조", "경조사·기타"))
	);

	public Entry of(Integer subcategoryId) {
		if (subcategoryId == null) {
			return Entry.EMPTY;
		}
		Entry entry = BY_SUBCATEGORY.get(subcategoryId);
		return entry == null ? Entry.EMPTY : entry;
	}

	public record Entry(String category, String subcategory) {
		static final Entry EMPTY = new Entry("", "");
	}
}
