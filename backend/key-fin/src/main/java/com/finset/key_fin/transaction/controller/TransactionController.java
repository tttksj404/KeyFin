package com.finset.key_fin.transaction.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.transaction.dto.request.TransactionClassificationRequest;
import com.finset.key_fin.transaction.dto.request.TransactionMemoUpdateRequest;
import com.finset.key_fin.transaction.dto.request.BulkTransactionClassificationRequest;
import com.finset.key_fin.transaction.dto.response.BulkTransactionClassificationResponse;
import com.finset.key_fin.transaction.dto.response.TransactionClassificationResponse;
import com.finset.key_fin.transaction.dto.response.TransactionListResponse;
import com.finset.key_fin.transaction.service.TransactionService;
import lombok.RequiredArgsConstructor;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@RestController
@RequestMapping("/api/v1/transactions")
@RequiredArgsConstructor
public class TransactionController implements TransactionControllerDocs {

	private final TransactionService transactionService;

	@GetMapping(produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<TransactionListResponse> getTransactions(
			@AuthenticationPrincipal Long userId,
			@RequestParam(required = false) String month,
			@RequestParam(required = false) Integer envelopeId,
			@RequestParam(required = false) Integer subcategoryId,
			@RequestParam(required = false) Long accountId,
			@RequestParam(required = false) Long cardId,
			@RequestParam(required = false) Long cursor,
			@RequestParam(required = false) Integer size
	) {
		return BaseResponse.ok(transactionService.getTransactions(
				userId, month, envelopeId, subcategoryId, accountId, cardId, cursor, size
		));
	}

	@GetMapping(value = "/pending", produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<TransactionListResponse> getPendingTransactions(
			@AuthenticationPrincipal Long userId,
			@RequestParam(required = false) Long cursor,
			@RequestParam(required = false) Integer size
	) {
		return BaseResponse.ok(transactionService.getPendingTransactions(userId, cursor, size));
	}

	@PutMapping(value = "/{id}/classification", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<TransactionClassificationResponse> classifyTransaction(
			@AuthenticationPrincipal Long userId,
			@PathVariable("id") Long transactionId,
			@RequestBody TransactionClassificationRequest request
	) {
		return BaseResponse.ok(transactionService.classifyTransaction(userId, transactionId, request));
	}

	@PutMapping(value = "/{id}/memo", consumes = APPLICATION_JSON_VALUE)
	@Override
	public ResponseEntity<Void> updateTransactionMemo(
			@AuthenticationPrincipal Long userId,
			@PathVariable("id") Long transactionId,
			@Valid @RequestBody TransactionMemoUpdateRequest request
	) {
		transactionService.updateTransactionMemo(userId, transactionId, request);
		return ResponseEntity.ok().build();
	}

	@PutMapping(value = "/classifications", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<BulkTransactionClassificationResponse> classifyPendingTransactions(
			@AuthenticationPrincipal Long userId,
			@Valid @RequestBody BulkTransactionClassificationRequest request
	) {
		return BaseResponse.ok(transactionService.classifyPendingTransactions(userId, request));
	}
}
