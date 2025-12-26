# 🛠️ Implementation Guide

## 1. Код для загрузки в System Prompt

```python
# src/core/prompt_builder.py

BLOCK_A_FILES = [
    "A1_StyleGuide_v1.txt",
    "A2_ISA_RoutingPrompts_v1.txt",
    "A3_Acceptance_Routing_v1.txt",
    "A4_Understanding_Entity_Routing_v1.txt",
    "A5_Opinion_Routing_v1.txt",
    "A6_Model_IO_Guide_v1.txt"
]

def build_system_prompt() -> str:
    """Загружает все 6 файлов Block A в System Prompt (~6,000 токенов)"""
    sections = []
    for filename in BLOCK_A_FILES:
        content = Path(f"knowledge/{filename}").read_text(encoding='utf-8')
        sections.append(f"# {filename}\n\n{content}")
    return "\n\n---\n\n".join(sections)
```

## 2. PostgreSQL таблицы (для A3-A5)

**A3 Acceptance:**
```sql
INSERT INTO acceptance_checks (
    project_id, client_name, decision, conflicts, confirmed_by
) VALUES (%s, %s, %s, %s, %s);
```

**A4 Understanding Entity:**
```sql
INSERT INTO risk_assessment (
    project_id, industry, key_risks, control_environment
) VALUES (%s, %s, %s, %s);
```

**A5 Opinion:**
```sql
UPDATE audit_reports
SET opinion_type = %s, modifications = %s
WHERE project_id = %s;
```

## 3. H2 Buttons пример (A3 Acceptance)

```python
return {
    "response": "Клиент TRI-S принят. Конфликтов не обнаружено.",
    "buttons": [
        {
            "label": "Сохранить",
            "action": "save-acceptance",
            "data": {
                "client": "TRI-S",
                "decision": "ACCEPTED",
                "conflicts": []
            }
        },
        {
            "label": "Отмена",
            "action": "cancel"
        }
    ]
}
```

## 4. TODO для разработчика

- [ ] Создать `src/core/prompt_builder.py`
- [ ] Протестировать загрузку всех 6 файлов (~6K токенов)
- [ ] Добавить H2 buttons для A3-A5 responses
- [ ] Подключить PostgreSQL (таблицы: acceptance_checks, risk_assessment, audit_reports)
- [ ] Написать тесты для prompt_builder

**Приоритет:** P1 (критический - это мозг системы)

## 5. Связанные документы

- G2 PostgreSQL Schema — таблицы для workflow
- Development Rules — H2 Buttons, Python Tools
