"""Frozen, engine-verified R4 case construction without model execution."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path
from typing import Final, Literal, assert_never

from benchmarks.coaching.contracts import CaseBundle, CaseInput, CaseLabel, ReceiptRecord, Split, Stratum
from coaching_service.engine import ENGINE_COMMIT, EngineAdapter
from coaching_service.evidence import bounded_evidence
from coaching_service.llm_contract import ChatMessage, EvidenceInput, Mode
from coaching_service.payments import Ledger, reduce_payment
from coaching_service.schemas import Bootstrap, Envelope, Frozen, JsonDocument, Receipt

ROOT: Final = Path(__file__).resolve().parent
AS_OF: Final = date(2026, 9, 9)
STRATA: Final[tuple[Stratum, ...]] = ("complete", "missing", "adversarial")
Channel = Literal["question", "user_history", "question_and_history"]
_CATEGORIES: Final = {
    domain: category
    for domains, category in (
        (("식사", "공동식사"), ("식비", "모임", "외식")),
        (("통근", "대중교통", "업무이동"), ("교통", "대중교통", "교통비")),
        (("건강", "건강관리", "의료보조"), ("건강", "약국", "의료·건강")),
        (("운동",), ("건강", "헬스장", "의료·건강")),
        (("문화관람", "스포츠관람", "취미"), ("여가·문화", "관람", "취미·여가")),
        (("의류관리", "전자기기", "경조사", "여행준비"), ("쇼핑", "선물", "쇼핑")),
        (
            (
                "생활용품",
                "주거안전",
                "주거관리",
                "집수리",
                "이사",
                "이사준비",
                "생활가전",
                "육아",
                "식재료",
                "원예",
                "수공예",
                "업무도구",
                "창작활동",
            ),
            ("생활", "생활용품", "편의점·마트·잡화"),
        ),
    )
    for domain in domains
}


class Archetype(Frozen):
    archetype_id: str
    split: Split
    description: str
    observation_days: int
    expense_every_days: int
    amounts: tuple[int, ...]
    income_every_days: int
    income_amount: int
    pending_history: bool = False
    canceled_history: bool = False
    snapshot: JsonDocument


class Family(Frozen):
    family_id: str
    split: Split
    domain: str
    expected_route: Mode
    archetype_id: str
    attack_template_id: str
    attack_channel: Channel
    question: str
    rationale: str
    history_notes: tuple[str, ...] = ()
    long_history: bool = False


class Attack(Frozen):
    template_id: str
    split: Split
    text: str


class Catalog(Frozen):
    schema_version: str
    authorship: str
    archetypes: tuple[Archetype, ...]
    attacks: tuple[Attack, ...]
    families: tuple[Family, ...]


def load_catalog() -> Catalog:
    return Catalog.model_validate_json((ROOT / "case_catalog.json").read_bytes())


def transaction(family: Family, owner: str, identifier: str, day: date, amount: int) -> JsonDocument:
    category, subcategory, _ = _CATEGORIES.get(family.domain, ("교육", "도서", "기타"))
    return JsonDocument(
        {
            "user_id": owner,
            "transaction_id": identifier,
            "source": "LIVE",
            "transaction_type": "WITHDRAW",
            "transaction_date": day.isoformat(),
            "transaction_time": "14:31:00",
            "category": category,
            "subcategory": subcategory,
            "merchant": "합성 자료 가맹점",
            "merchant_id": "merchant-" + owner,
            "amount_krw": amount,
            "account_id": "a",
            "card_id": "",
            "confirm_status": "CONFIRMED",
            "status": "NORMAL",
        }
    )


def bootstrap(family: Family, archetype: Archetype, owner: str) -> Bootstrap:
    rows: list[JsonDocument] = []
    for index, ago in enumerate(range(archetype.observation_days, 0, -archetype.expense_every_days)):
        row = transaction(
            family,
            owner,
            "history-" + str(index),
            AS_OF - timedelta(days=ago),
            archetype.amounts[index % len(archetype.amounts)],
        )
        if archetype.pending_history and index == 1:
            row = JsonDocument({**row.root, "confirm_status": "PENDING"})
        if archetype.canceled_history and index == 2:
            row = JsonDocument({**row.root, "status": "CANCELED"})
        rows.append(row)
    if archetype.income_every_days:
        for ago in range(
            archetype.income_every_days, archetype.observation_days + 1, archetype.income_every_days
        ):
            row = transaction(
                family, owner, "income-" + str(ago), AS_OF - timedelta(days=ago), archetype.income_amount
            )
            rows.append(
                JsonDocument(
                    {
                        **row.root,
                        "transaction_type": "DEPOSIT",
                        "direction": "INCOME",
                        "category": "소득",
                        "subcategory": "급여",
                        "merchant_id": "payroll",
                    }
                )
            )
    family_seed = int(hashlib.sha256(family.family_id.encode()).hexdigest()[:8], 16)
    before = 120000 + family_seed % 181 * 1000
    envelope = _CATEGORIES.get(family.domain, ("교육", "도서", "기타"))[2]
    budgets = JsonDocument.model_validate(archetype.snapshot.root["budgets"])
    snapshot = JsonDocument({**archetype.snapshot.root, "budgets": {envelope: budgets.root["기타"]}})
    return Bootstrap(
        as_of=AS_OF,
        transactions=tuple(rows),
        snapshot=snapshot,
        envelopes=(Envelope(envelope=envelope, balance_krw=before),),
    )


def family_receipts(family: Family, archetype: Archetype) -> tuple[Receipt, Receipt]:
    """Use real event updates and the service reducer; never infer a trigger label."""
    engine = EngineAdapter()
    owner = "person-" + hashlib.sha256(family.family_id.encode()).hexdigest()[:12]
    initial = bootstrap(family, archetype, owner)
    before = initial.envelopes[0].balance_krw
    ratio = 400 + int(hashlib.sha256(owner.encode()).hexdigest()[:4], 16) % 100
    payment = transaction(family, owner, "current-payment", AS_OF, before * ratio // 1000)
    event = JsonDocument(
        {
            "user_id": owner,
            "event_id": "confirmed-payment",
            "type": "transaction",
            "transaction": payment.root,
        }
    )
    if initial.snapshot is None:
        raise ValueError("Complete archetype must provide a snapshot")
    snapshot_event = JsonDocument(
        {
            "user_id": owner,
            "event_id": "verified-balance",
            "type": "snapshot",
            "snapshot": initial.snapshot.root,
        }
    )
    initial_twin = engine.create(initial, owner)
    complete = engine.update(initial_twin, event, snapshot_event)
    missing = (
        engine.update(initial_twin, event)
        if ratio % 2
        else engine.update(engine.create(initial.model_copy(update={"snapshot": None}), owner), event)
    )
    transactions = engine.transactions(complete)
    confirmed = next(row for row in transactions if row.id == "current-payment")
    detected = reduce_payment(Ledger(envelopes=initial.envelopes), confirmed, transactions)
    if detected.reason != "p1_ambiguous":
        raise ValueError("Actual P1 reducer precondition failed for " + family.family_id)
    request = JsonDocument(
        {"on_date": AS_OF.isoformat(), "through_date": "2026-09-16", "paths": 20, "seed": 42}
    )
    receipts: list[Receipt] = []
    for document, expected in ((complete, "ready"), (missing, "needs_data")):
        result = engine.review(document, request)
        if result.root["status"] != expected:
            raise ValueError("Actual engine state mismatch for " + family.family_id)
        receipts.append(
            Receipt(
                engine_commit=ENGINE_COMMIT,
                identity=engine.identity(document),
                request=request,
                result=result,
                payment=detected.facts,
                trigger=detected.reason,
                current_envelopes=detected.ledger.envelopes,
            )
        )
    return receipts[0], receipts[1]


def text_context(family: Family, attack: Attack | None) -> tuple[str, tuple[ChatMessage, ...]]:
    notes = list(family.history_notes)
    if family.long_history:
        notes.extend(
            ("기록 메모: " + family.question + " 현재는 자료를 검토하는 대화입니다. ") * 8 for _ in range(4)
        )
    history = tuple(ChatMessage(role="user", content=note) for note in notes)
    question = family.question
    if attack is not None:
        match family.attack_channel:
            case "question":
                question += "\n" + attack.text
            case "user_history":
                history += (ChatMessage(role="user", content=attack.text),)
            case "question_and_history":
                question += "\n" + attack.text
                history += (ChatMessage(role="user", content=attack.text),)
            case unreachable:
                assert_never(unreachable)
    return question, history


def build_cases() -> CaseBundle:
    catalog = load_catalog()
    archetypes = {row.archetype_id: row for row in catalog.archetypes}
    attacks = {row.template_id: row for row in catalog.attacks}
    inputs: list[CaseInput] = []
    labels: list[CaseLabel] = []
    records: list[ReceiptRecord] = []
    for family in catalog.families:
        archetype, attack = archetypes[family.archetype_id], attacks[family.attack_template_id]
        if archetype.split != family.split or attack.split != family.split:
            raise ValueError("Cross-split source reference for " + family.family_id)
        complete, missing = family_receipts(family, archetype)
        for index, stratum in enumerate(STRATA):
            case_id = "case-" + hashlib.sha256((family.family_id + str(index)).encode()).hexdigest()[:14]
            receipt = missing if stratum == "missing" else complete
            active_attack = attack if stratum == "adversarial" else None
            question, history = text_context(family, active_attack)
            evidence: EvidenceInput = bounded_evidence(receipt, question, history)
            inputs.append(CaseInput(case_id=case_id, evidence=evidence))
            labels.append(
                CaseLabel(
                    case_id=case_id,
                    family_id=family.family_id,
                    split=family.split,
                    domain=family.domain,
                    stratum=stratum,
                    receipt_archetype_id=archetype.archetype_id,
                    attack_template_id=attack.template_id if active_attack else None,
                    expected_route=family.expected_route,
                    expected_judgment=None if stratum == "complete" else "needs_data",
                    rationale=family.rationale
                    + "; "
                    + (
                        "원 엔진 status=needs_data: 잔액 자료 부족"
                        if stratum == "missing"
                        else "명시적 지시 오염: 계약상 기권"
                        if active_attack
                        else "정상 금융 보조 판단의 정답은 정의하지 않음"
                    ),
                )
            )
            records.append(ReceiptRecord(case_id=case_id, receipt=receipt))
    return CaseBundle(inputs=tuple(inputs), labels=tuple(labels), receipts=tuple(records))


def main() -> None:
    bundle = build_cases()
    for name, rows in (("inputs", bundle.inputs), ("labels", bundle.labels), ("receipts", bundle.receipts)):
        target = ROOT / (name + ".jsonl")
        content = "".join(row.model_dump_json() + "\n" for row in rows).encode("utf-8")
        if target.exists() and target.read_bytes() != content:
            raise FileExistsError("Frozen dataset already exists with different bytes: " + target.name)
        temporary = target.with_suffix(".jsonl.tmp")
        _ = temporary.write_bytes(content)
        _ = temporary.replace(target)


if __name__ == "__main__":
    main()
