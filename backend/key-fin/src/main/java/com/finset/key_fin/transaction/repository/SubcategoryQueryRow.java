package com.finset.key_fin.transaction.repository;

public record SubcategoryQueryRow(
		Integer envelopeId,
		String envelopeName,
		Integer subcategoryId,
		String subcategoryName
) {
}
