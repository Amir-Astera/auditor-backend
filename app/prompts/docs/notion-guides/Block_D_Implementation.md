# 🛠️ Implementation Guide

## 1. RAG для деревьев решений (D2, D3, D4)

```python
# src/rag/block_d_indexer.py

BLOCK_D_SIMPLE_TREES = [
    "D2_Acceptance_Continuance_ISQM1_ISA220_Tree_v1.txt",  # 4 узла
    "D3_Opinion_Decision_Tree_ISA700_705_706_v1.txt",      # 6 узлов
    "D4_GoingConcern_Decision_Tree_ISA570_v1.txt"          # 4 узла
]

def index_decision_trees():
    """Векторизация деревьев D2-D4 в Qdrant"""
    for filename in BLOCK_D_SIMPLE_TREES:
        content = Path(f"knowledge/{filename}").read_text(encoding='utf-8')

        # Chunking по секциям (NODE A1, NODE A2, ...)
        chunks = chunk_by_section(content, marker="^NODE")

        for chunk in chunks:
            qdrant_client.upsert(
                collection_name="oson_knowledge",
                points=[{
                    "id": generate_id(filename, chunk.index),
                    "vector": embed(chunk.text),
                    "payload": {
                        "block": "D",
                        "file_id": extract_file_id(filename),
                        "tree_type": extract_tree_type(filename),  # acceptance, opinion, gc
                        "decision_nodes": count_nodes(content),
                        "outcomes": extract_outcomes(content),
                        "text": chunk.text
                    }
                }]
            )
```

## 2. Python Tool для D1 Legal Matrix

```python
# src/tools/legal_assessment.py

def assess_legal_matter(
    claim_amount: float,
    probability: str,         # "probable" | "possible" | "remote"
    pm: float,
    outcome_estimable: bool
) -> dict:
    """
    IAS 37 + ISA 501 логика для legal matters.
    """
    is_material = claim_amount >= pm

    # IAS 37 decision logic
    if probability == "probable" and outcome_estimable:
        provision_required = True
        disclosure_required = True
        fs_action = "Provision"
    elif probability == "possible":
        provision_required = False
        disclosure_required = True
        fs_action = "Contingent Liability Disclosure"
    else:  # remote
        provision_required = False
        disclosure_required = False
        fs_action = "None"

    # KAM escalation (если material + critical)
    is_kam = is_material and claim_amount >= 2 * pm

    return {
        "is_material": is_material,
        "disclosure_required": disclosure_required,
        "provision_required": provision_required,
        "is_kam": is_kam,
        "fs_action": fs_action,
        "rationale": f"IAS 37: {probability} + estimable={outcome_estimable}"
    }
```

## 3. PostgreSQL таблицы

```sql
-- Client acceptance decisions
CREATE TABLE client_acceptance (
    acceptance_id SERIAL PRIMARY KEY,
    project_id VARCHAR(50) REFERENCES projects(project_id),
    independence_threats BOOLEAN,
    integrity_concerns BOOLEAN,
    competence_adequate BOOLEAN,
    preconditions_met BOOLEAN,
    decision VARCHAR(50),  -- 'ACCEPT' | 'REJECT' | 'ESCALATE'
    rationale TEXT,
    confirmed_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Legal matters register (D1)
CREATE TABLE legal_matters (
    legal_id VARCHAR(50) PRIMARY KEY,
    project_id VARCHAR(50) REFERENCES projects(project_id),
    claim_amount NUMERIC(15,2),
    probability VARCHAR(20),
    provision_required BOOLEAN,
    disclosure_required BOOLEAN,
    is_kam BOOLEAN,
    fs_action VARCHAR(100),
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Going concern assessment (D4)
CREATE TABLE going_concern (
    gc_id SERIAL PRIMARY KEY,
    project_id VARCHAR(50) REFERENCES projects(project_id),
    indicators_present BOOLEAN,
    material_uncertainty BOOLEAN,
    disclosure_adequate BOOLEAN,
    eom_required BOOLEAN,
    opinion_impact VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 4. LLM Reasoning Example (D3 Opinion Tree)

```python
# Пользователь: "SUD $240K, PM $300K. Какое мнение?"

# 1. RAG → retrieve D3 tree
context = retrieve_from_qdrant(query="opinion decision tree", file_id="D3")

# 2. LLM делает Chain-of-Thought reasoning:
"""
O1: Material misstatements?
   SUD $240K < PM $300K → NOT material

O4: Material scope limitation? → NO

O7: Going concern uncertainty? → NO

Final outcome: UNMODIFIED
"""

# 3. Response
return {
    "response": "Unmodified opinion. SUD ниже PM порога.",
    "rationale": "Checked nodes O1→O4→O7: no issues"
}
```

## 5. TODO для разработчика

- [ ] Векторизовать D2, D3, D4 в Qdrant (section-based chunking)
- [ ] Имплементировать `assess_legal_matter()` Python tool для D1
- [ ] Создать таблицы: `client_acceptance`, `legal_matters`, `going_concern`
- [ ] Написать тесты для LLM reasoning на деревьях D2-D4
- [ ] Интеграция D3 с G2.11 (Opinion table)
- [ ] Связать D1 с G1_Client (legal letters from clients)

**Приоритет:** P2 (важный, но зависит от Block C materiality)

## 6. Связанные документы

- G1 Qdrant Design — RAG для деревьев решений
- G2 PostgreSQL Schema — таблицы legal_matters, going_concern
- Functions I1-I10 — I3: assess_legal_matter()
