package com.finset.key_fin.transaction.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.transaction.dto.response.SubcategoryListResponse;
import com.finset.key_fin.transaction.dto.response.SubcategoryListResponse.EnvelopeItem;
import com.finset.key_fin.transaction.dto.response.SubcategoryListResponse.SubcategoryItem;
import com.finset.key_fin.transaction.repository.SubcategoryQueryRepository;
import com.finset.key_fin.transaction.repository.SubcategoryQueryRow;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class SubcategoryService {

	private final UserRepository userRepository;
	private final SubcategoryQueryRepository subcategoryQueryRepository;

	@Transactional(readOnly = true)
	public SubcategoryListResponse getSubcategories(long userId) {
		validateActiveUser(userId);
		List<SubcategoryQueryRow> rows = subcategoryQueryRepository.findAllWithEnvelope();

		Map<Integer, EnvelopeGroup> envelopeGroups = new LinkedHashMap<>();
		for (SubcategoryQueryRow row : rows) {
			EnvelopeGroup envelopeGroup = envelopeGroups.get(row.envelopeId());
			if (envelopeGroup == null) {
				envelopeGroup = new EnvelopeGroup(row.envelopeId(), row.envelopeName());
				envelopeGroups.put(row.envelopeId(), envelopeGroup);
			}
			envelopeGroup.addSubcategory(row.subcategoryId(), row.subcategoryName());
		}

		List<EnvelopeItem> items = envelopeGroups.values().stream()
				.map(EnvelopeGroup::toResponse)
				.toList();
		return new SubcategoryListResponse(items);
	}

	private void validateActiveUser(long userId) {
		if (userRepository.findByIdAndDeletedAtIsNull(userId).isEmpty()) {
			throw new BusinessException(UserErrorCode.USER_NOT_FOUND);
		}
	}

	private static class EnvelopeGroup {
		private final Integer envelopeId;
		private final String envelopeName;
		private final List<SubcategoryItem> subcategories = new ArrayList<>();

		private EnvelopeGroup(Integer envelopeId, String envelopeName) {
			this.envelopeId = envelopeId;
			this.envelopeName = envelopeName;
		}

		private void addSubcategory(Integer id, String name) {
			subcategories.add(new SubcategoryItem(id, name));
		}

		private EnvelopeItem toResponse() {
			return new EnvelopeItem(envelopeId, envelopeName, List.copyOf(subcategories));
		}
	}
}
