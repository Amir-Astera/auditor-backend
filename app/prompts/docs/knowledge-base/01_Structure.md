# Knowledge Base Structure

> [← INDEX](../INDEX.md) | [Files Index →](./02_Files_Index.md)

---

## Overview

База знаний организована в 6 блоков (A-F). Каждый блок имеет своё назначение и способ хранения.

---

## Blocks

```
/knowledge/
├── A_Routing/          # System prompts (в промпт, НЕ векторизуется)
├── B_Libraries/        # Справочники → Qdrant
├── C_Formulas/         # Формулы расчётов → Qdrant
├── D_DecisionTrees/    # Деревья решений → Qdrant
├── E_Templates/        # Шаблоны документов → MinIO
└── F_Knowledge/        # Общие знания → Qdrant
```

---

## Block A: Routing (System Prompts)

**Хранение:** В промпт LLM (не векторизуется)
**Назначение:** Настройка поведения и стиля ответов

| File | Description |
|------|-------------|
| A1_StyleGuide_v1.txt | Стиль ответов, форматирование |
| A2_ISA_RoutingPrompts_v1.txt | Routing по ISA стандартам |
| A3_Acceptance_Routing_v1.txt | Acceptance & Continuance |
| A4_Understanding_Entity_Routing_v1.txt | Understanding the Entity |
| A5_Opinion_Routing_v1.txt | Opinion формирование |
| A6_Model_IO_Guide_v1.txt | Input/Output guide для модели |

---

## Block B: Libraries (Справочники)

**Хранение:** Qdrant (векторизация)
**Назначение:** Справочная информация для RAG

| File | ISA | Description |
|------|-----|-------------|
| B1_Risk_Library_by_Cycle_v1.txt | ISA 315 | Библиотека рисков по циклам |
| B2_PBC_Master_List_v1.txt | ISA 500 | Master list запрашиваемых документов |
| B3_Glossary_EN-RU-UZ_v1.txt | — | Глоссарий терминов |
| B4_Fraud_Risk_Factors_ISA240_v1.txt | ISA 240 | Факторы риска мошенничества |
| B5_Estimates_ISA540_Library_v1.txt | ISA 540 | Библиотека оценочных значений |
| B6_GoingConcern_ISA570_Indicators_v1.txt | ISA 570 | Индикаторы непрерывности |
| B7_RelatedParties_ISA550_Checklist_v1.txt | ISA 550 | Чеклист связанных сторон |
| B8_SubsequentEvents_ISA560_Library_v1.txt | ISA 560 | События после отчётной даты |

---

## Block C: Formulas (Формулы)

**Хранение:** Qdrant (векторизация) + Python Tools
**Назначение:** Формулы и методики расчётов

| File | ISA | Description |
|------|-----|-------------|
| C1_Materiality_Playbook_v1.1.txt | ISA 320 | Playbook расчёта существенности |
| C2_Sampling_Methods_ISA530_v1.txt | ISA 530 | Методы выборки |
| C4_Testing_Procedures_ISA500_520_530_v1.txt | ISA 500/520/530 | Процедуры тестирования |
| C5_Misstatements_ISA450_Formulas_v1.txt | ISA 450 | Формулы искажений |

---

## Block D: Decision Trees

**Хранение:** Qdrant (векторизация)
**Назначение:** Деревья решений для сложных judgments

| File | ISA | Description |
|------|-----|-------------|
| D1_Legal_Matrix_ISA560_501_v1.txt | ISA 501/560 | Матрица судебных дел |
| D2_Acceptance_Continuance_ISQM1_ISA220_Tree_v1.txt | ISQM1/ISA 220 | Acceptance tree |
| D3_Opinion_Decision_Tree_ISA700_705_706_v1.txt | ISA 700-706 | Opinion tree |
| D4_GoingConcern_Decision_Tree_ISA570_v1.txt | ISA 570 | Going concern tree |

---

## Block E: Templates

**Хранение:** MinIO (файлы)
**Назначение:** Шаблоны для генерации документов

| File | ISA | Description |
|------|-----|-------------|
| E0_Audit_Templates_Master_v1.1.txt | — | Master index шаблонов |
| E1_TCWG_Communication_Pack_v1.txt | ISA 260/265 | Коммуникации TCWG |
| E2_KAM_Skeletons_ISA701_v1.txt | ISA 701 | Скелеты KAM |
| E3_Engagement_Letter_ISA210_Template_v1.txt | ISA 210 | Письмо о задании |
| E4_Management_Representation_Letter_ISA580_Template_v1.txt | ISA 580 | Письмо руководства |
| E5_Audit_Report_Templates_ISA700_705_706_v1.txt | ISA 700-706 | Шаблоны заключений |
| E6_Management_Letter_ISA265_Template_v1.txt | ISA 265 | Management letter |
| E7-E42... | Various | Рабочие программы по циклам |

---

## Block F: Knowledge

**Хранение:** Qdrant (векторизация)
**Назначение:** Контекстные знания

| File | Description |
|------|-------------|
| F1_Company_Profile_TRI-S-Audit_v1.txt | Профиль аудиторской компании |
| F2_Industry_Knowledge_Pack_v1.txt | Отраслевые знания |

---

## Storage Matrix

| Block | Qdrant | MinIO | In Prompt |
|-------|--------|-------|-----------|
| A | — | — | ✅ |
| B | ✅ | — | — |
| C | ✅ | — | — |
| D | ✅ | — | — |
| E | — | ✅ | — |
| F | ✅ | — | — |

---

## Indexing Commands

```bash
# Index all knowledge blocks to Qdrant
python scripts/index_knowledge.py --path /knowledge/B_Libraries/
python scripts/index_knowledge.py --path /knowledge/C_Formulas/
python scripts/index_knowledge.py --path /knowledge/D_DecisionTrees/
python scripts/index_knowledge.py --path /knowledge/F_Knowledge/

# Or index all at once
python scripts/index_knowledge.py --all
```

---

## Related Docs

- [Files Index](./02_Files_Index.md) — Полный список файлов
- [Data Circuits](../architecture/03_Data_Circuits.md) — Circuit 1 (Static KB)
