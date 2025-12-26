# Knowledge Base Files Index

> [← Structure](./01_Structure.md) | [Guides →](../guides/Development_Rules.md)

---

## Overview

Полный индекс файлов Knowledge Base. **65 файлов** в production.

---

## Block A: Routing (System Prompts)

**Storage:** In LLM Prompt (not vectorized)
**Files:** 6

| File | Description | Status |
|------|-------------|--------|
| A1_StyleGuide_v1.txt | Стиль ответов, форматирование | ✅ |
| A2_ISA_RoutingPrompts_v1.txt | Routing по ISA стандартам | ✅ |
| A3_Acceptance_Routing_v1.txt | Acceptance & Continuance | ⏳ |
| A4_Understanding_Entity_Routing_v1.txt | Understanding the Entity | ⏳ |
| A5_Opinion_Routing_v1.txt | Opinion формирование | ⏳ |
| A6_Model_IO_Guide_v1.txt | Input/Output guide для модели | ✅ |

---

## Block B: Libraries (Справочники)

**Storage:** Qdrant (vectorized)
**Files:** 8

| File | ISA/IFRS | Description | Status |
|------|----------|-------------|--------|
| B1_Risk_Library_by_Cycle_v1.txt | ISA 315 | Библиотека рисков по циклам | ✅ |
| B2_PBC_Master_List_v1.txt | ISA 500 | Master list запрашиваемых документов | ✅ |
| B3_Glossary_EN-RU-UZ_v1.txt | — | Глоссарий терминов | ✅ |
| B4_Fraud_Risk_Factors_ISA240_v1.txt | ISA 240 | Факторы риска мошенничества | ⏳ |
| B5_Estimates_ISA540_Library_v1.txt | ISA 540 | Библиотека оценочных значений | ⏳ |
| B6_GoingConcern_ISA570_Indicators_v1.txt | ISA 570 | Индикаторы непрерывности | ⏳ |
| B7_RelatedParties_ISA550_Checklist_v1.txt | ISA 550 | Чеклист связанных сторон | ⏳ |
| B8_SubsequentEvents_ISA560_Library_v1.txt | ISA 560 | События после отчётной даты | ⏳ |

---

## Block C: Formulas (Формулы)

**Storage:** Qdrant (vectorized) + Python Tools
**Files:** 4

| File | ISA/IFRS | Description | Status |
|------|----------|-------------|--------|
| C1_Materiality_Playbook_v1.1.txt | ISA 320 | Playbook расчёта существенности | ⏳ |
| C2_Sampling_Methods_ISA530_v1.txt | ISA 530 | Методы выборки | ⏳ |
| C4_Testing_Procedures_ISA500_520_530_v1.txt | ISA 500/520/530 | Процедуры тестирования | ⏳ |
| C5_Misstatements_ISA450_Formulas_v1.txt | ISA 450 | Формулы искажений | ⏳ |

---

## Block D: Decision Trees

**Storage:** Qdrant (vectorized)
**Files:** 4

| File | ISA/IFRS | Description | Status |
|------|----------|-------------|--------|
| D1_Legal_Matrix_ISA560_501_v1.txt | ISA 501/560 | Матрица судебных дел | ⏳ |
| D2_Acceptance_Continuance_ISQM1_ISA220_Tree_v1.txt | ISQM1/ISA 220 | Acceptance tree | ⏳ |
| D3_Opinion_Decision_Tree_ISA700_705_706_v1.txt | ISA 700-706 | Opinion tree | ⏳ |
| D4_GoingConcern_Decision_Tree_ISA570_v1.txt | ISA 570 | Going concern tree | ⏳ |

---

## Block E: Templates

**Storage:** MinIO (file storage)
**Files:** 41

### Core Templates (E0-E9)

| File | ISA/IFRS | Description | Status |
|------|----------|-------------|--------|
| E0_Audit_Templates_Master_v1.1.txt | — | Master index шаблонов | ⏳ |
| E1_TCWG_Communication_Pack_v1.txt | ISA 260/265 | Коммуникации TCWG | ⏳ |
| E2_KAM_Skeletons_ISA701_v1.txt | ISA 701 | Скелеты KAM | ⏳ |
| E3_Engagement_Letter_ISA210_Template_v1.txt | ISA 210 | Письмо о задании | ⏳ |
| E4_Management_Representation_Letter_ISA580_Template_v1.txt | ISA 580 | Письмо руководства | ⏳ |
| E5_Audit_Report_Templates_ISA700_705_706_v1.txt | ISA 700-706 | Шаблоны заключений | ⏳ |
| E6_Management_Letter_ISA265_Template_v1.txt | ISA 265 | Management letter | ⏳ |
| E7_Audit_Completion_Memorandum_ACM_v1.txt | — | Меморандум завершения | ⏳ |
| E8_SUD_Summary_of_Unadjusted_Misstatements_v1.txt | ISA 450 | Summary of Unadjusted Differences | ⏳ |
| E9_Audit_Planning_Memorandum_APM_v1.txt | ISA 300 | Планирование аудита | ⏳ |

### Risk & Control Templates (E10-E16)

| File | ISA/IFRS | Description | Status |
|------|----------|-------------|--------|
| E10_Significant_Risk_Matrix_SRM_v1.txt | ISA 315 | Матрица значимых рисков | ⏳ |
| E11_Journal_Entries_Testing_Template_ISA240_v1.txt | ISA 240 | Тестирование проводок | ⏳ |
| E12_Subsequent_Events_Procedures_ISA560_v1.txt | ISA 560 | Процедуры СПОД | ⏳ |
| E13_Going_Concern_Worksheet_ISA570_v1.txt | ISA 570 | Рабочий лист непрерывности | ⏳ |
| E14_Related_Parties_Audit_Program_ISA550_v1.txt | ISA 550 | Программа связанных сторон | ⏳ |
| E15_Audit_Evidence_Summary_ISA500_v1.txt | ISA 500 | Summary аудиторских доказательств | ⏳ |
| E16_Estimates_Audit_Program_ISA540_v1.txt | ISA 540 | Программа оценочных значений | ⏳ |

### Substantive Programs by Cycle (E17-E37)

| File | ISA/IFRS | Description | Status |
|------|----------|-------------|--------|
| E17_Inventory_Count_Audit_Program_ISA501_v1.txt | ISA 501 | Инвентаризация | ⏳ |
| E18_Revenue_Recognition_Program_ISA240_IFRS15_v1.txt | ISA 240/IFRS 15 | Признание выручки | ⏳ |
| E19_PPE_Audit_Program_IAS16_ISA500_v1.txt | IAS 16 | Основные средства | ⏳ |
| E20_Cash_and_Bank_Program_ISA505_v1.txt | ISA 505 | Денежные средства | ⏳ |
| E21_Accounts_Receivable_Program_ISA505_IFRS9_v1.txt | ISA 505/IFRS 9 | Дебиторская задолженность | ⏳ |
| E22_Accounts_Payable_and_Expenses_Program_ISA330_v1.txt | ISA 330 | Кредиторская задолженность | ⏳ |
| E23_Payroll_Audit_Program_ISA330_v1.txt | ISA 330 | Заработная плата | ⏳ |
| E24_Investments_Fair_Value_Program_IFRS9_IFRS13_v1.txt | IFRS 9/13 | Инвестиции и справедливая стоимость | ⏳ |
| E25_Inventory_Costing_Program_IAS2_v1.txt | IAS 2 | Себестоимость запасов | ⏳ |
| E26_Income_Tax_Audit_Program_IAS12_v1.txt | IAS 12 | Налог на прибыль | ⏳ |
| E27_Provisions_Contingencies_Program_IAS37_v1.txt | IAS 37 | Резервы и условные обязательства | ⏳ |
| E28_Intangibles_Goodwill_Program_IAS38_IFRS3_IAS36_v1.txt | IAS 38/IFRS 3/IAS 36 | НМА и гудвилл | ⏳ |
| E29_Leases_Program_IFRS16_v1.txt | IFRS 16 | Аренда | ⏳ |
| E30_Financial_Statement_Disclosure_Checklist_IAS1_ISA700_v1.txt | IAS 1/ISA 700 | Чеклист раскрытий | ⏳ |
| E31_IFRS15_Revenue_Audit_Program_Extended_v1.txt | IFRS 15 | Расширенная программа выручки | ⏳ |
| E32_Cash_Flow_Statement_Program_IAS7_v1.txt | IAS 7 | Отчёт о движении денег | ⏳ |
| E33_Segment_Reporting_Program_IFRS8_v1.txt | IFRS 8 | Сегментная отчётность | ⏳ |
| E34_Equity_Capital_Program_IAS1_IAS32_IFRS2_v1.txt | IAS 1/32/IFRS 2 | Капитал и акции | ⏳ |
| E35_Consolidation_Group_Audit_Program_IFRS10_IFRS12_IAS28_v1.txt | IFRS 10/12/IAS 28 | Консолидация | ⏳ |
| E36_Joint_Arrangements_Associates_IFRS11_IAS28_v1.txt | IFRS 11/IAS 28 | СП и ассоциированные компании | ⏳ |
| E37_Financial_Instruments_Disclosures_IFRS7_v1.txt | IFRS 7 | Раскрытия фин.инструментов | ⏳ |

### Industry-Specific Programs (E39-E42)

| File | ISA/IFRS | Description | Status |
|------|----------|-------------|--------|
| E39_Biological_Assets_Agriculture_IAS41_v1.txt | IAS 41 | Биологические активы | ⏳ |
| E40_Investment_Property_IAS40_IFRS13_v1.txt | IAS 40/IFRS 13 | Инвестиционная недвижимость | ⏳ |
| E42_IFRS17_Insurance_Contracts_Audit_Program_v1.txt | IFRS 17 | Страховые контракты | ⏳ |

---

## Block F: Knowledge

**Storage:** Qdrant (vectorized)
**Files:** 2

| File | Description | Status |
|------|-------------|--------|
| F1_Company_Profile_TRI-S-Audit_v1.txt | Профиль аудиторской компании | ⏳ |
| F2_Industry_Knowledge_Pack_v1.txt | Отраслевые знания | ⏳ |

---

## Statistics

| Block | Total | Ready | In Progress | Storage |
|-------|-------|-------|-------------|---------|
| A | 6 | 3 | 3 | In Prompt |
| B | 8 | 3 | 5 | Qdrant |
| C | 4 | 0 | 4 | Qdrant + Python |
| D | 4 | 0 | 4 | Qdrant |
| E | 41 | 0 | 41 | MinIO |
| F | 2 | 0 | 2 | Qdrant |
| **Total** | **65** | **6** | **59** | — |

---

## ISA/IFRS Coverage

### ISA Standards

| ISA | Files | Coverage |
|-----|-------|----------|
| ISA 200 | A2 | ✅ |
| ISA 210 | E3 | ✅ |
| ISA 220 | D2 | ✅ |
| ISA 240 | B4, E11, E18 | ✅ |
| ISA 260 | E1 | ✅ |
| ISA 265 | E1, E6 | ✅ |
| ISA 300 | E9 | ✅ |
| ISA 315 | B1, E10 | ✅ |
| ISA 320 | C1 | ✅ |
| ISA 330 | E22, E23 | ✅ |
| ISA 450 | C5, E8 | ✅ |
| ISA 500 | B2, C4, E15 | ✅ |
| ISA 501 | D1, E17 | ✅ |
| ISA 505 | E20, E21 | ✅ |
| ISA 520 | C4 | ✅ |
| ISA 530 | C2, C4 | ✅ |
| ISA 540 | B5, E16 | ✅ |
| ISA 550 | B7, E14 | ✅ |
| ISA 560 | B8, D1, E12 | ✅ |
| ISA 570 | B6, D4, E13 | ✅ |
| ISA 580 | E4 | ✅ |
| ISA 700 | E5, D3, E30 | ✅ |
| ISA 701 | E2 | ✅ |
| ISA 705 | E5, D3 | ✅ |
| ISA 706 | E5, D3 | ✅ |
| ISQM 1 | D2 | ✅ |

### IFRS/IAS Standards

| IFRS/IAS | Files | Coverage |
|----------|-------|----------|
| IAS 1 | E30, E34 | ✅ |
| IAS 2 | E25 | ✅ |
| IAS 7 | E32 | ✅ |
| IAS 12 | E26 | ✅ |
| IAS 16 | E19 | ✅ |
| IAS 28 | E35, E36 | ✅ |
| IAS 32 | E34 | ✅ |
| IAS 36 | E28 | ✅ |
| IAS 37 | E27 | ✅ |
| IAS 38 | E28 | ✅ |
| IAS 40 | E40 | ✅ |
| IAS 41 | E39 | ✅ |
| IFRS 2 | E34 | ✅ |
| IFRS 3 | E28 | ✅ |
| IFRS 7 | E37 | ✅ |
| IFRS 8 | E33 | ✅ |
| IFRS 9 | E21, E24 | ✅ |
| IFRS 10 | E35 | ✅ |
| IFRS 11 | E36 | ✅ |
| IFRS 12 | E35 | ✅ |
| IFRS 13 | E24, E40 | ✅ |
| IFRS 15 | E18, E31 | ✅ |
| IFRS 16 | E29 | ✅ |
| IFRS 17 | E42 | ✅ |

---

## Related Docs

- [Structure](./01_Structure.md) — Block descriptions
- [Data Circuits](../architecture/03_Data_Circuits.md) — Circuit 1 (Static KB)
