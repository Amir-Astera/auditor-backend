# Crawlers Sources (Circuit 3)

> [← Data Circuits](./03_Data_Circuits.md) | [INDEX](../INDEX.md)

---

## Overview

Полный список источников для веб-краулеров. Разделён по категориям с указанием частоты обновления.

---

## 1. Global Standards (Глобальные стандарты)

| URL | Организация | Контент |
|-----|-------------|---------|
| https://www.ifrs.org/ | IFRS Foundation | Тексты стандартов МСФО |
| https://www.ifac.org/ | IFAC | Кодексы этики |
| https://www.iaasb.org/ | IAASB | Стандарты МСА (ISA) |
| https://www.coso.org/ | COSO | Управление рисками, IC |
| https://www.theiia.org/ | IIA | Стандарты внутреннего аудита |

**Частота:** Reference (при выходе обновлений)

---

## 2. Fraud & Forensic (Форензик)

| URL | Организация | Контент |
|-----|-------------|---------|
| https://www.acfe.com/ | ACFE | Методики расследования мошенничества |
| https://www.aicpa.org/ | AICPA | Стандарты для экспертов-свидетелей |
| https://forensicglobal.org/ | ICFA | Обучающие материалы |
| https://www.justice.gov/ | DOJ (USA) | Прецеденты по коррупции |
| https://www.sfo.gov.uk/ | SFO (UK) | Кейсы по крупному мошенничеству |

**Частота:** Reference (квартально)

---

## 3. Compliance, KYC & AML

| URL | Организация | Контент |
|-----|-------------|---------|
| https://www.fatf-gafi.org/ | FATF | Стандарты AML/CFT, списки стран |
| https://ofac.treasury.gov/ | OFAC (USA) | Санкционные списки (SDN List) |
| https://www.transparency.org/ | TI | Индекс восприятия коррупции (CPI) |
| https://opencorporates.com/ | OpenCorporates | База юридических лиц |
| https://www.worldbank.org/ | World Bank | Debarment List |

**Частота:**
- OFAC SDN List: ежедневно
- Остальные: ежемесячно

---

## 4. US Regulation

| URL | Организация | Контент |
|-----|-------------|---------|
| https://www.sec.gov/ | SEC | База EDGAR, законодательство |
| https://pcaobus.org/ | PCAOB | Надзор за аудитом |
| https://www.fasb.org/ | FASB | Стандарты US GAAP |
| https://www.irs.gov/ | IRS | Налоговые коды и формы |
| https://www.fincen.gov/ | FinCEN | Правила KYC, SAR |
| https://www.investopedia.com/ | Investopedia | Определения терминов |

**Частота:**
- SEC EDGAR: требует специфический парсер
- Investopedia: Dynamic (инкрементально)

---

## 5. UK Regulation

| URL | Организация | Контент |
|-----|-------------|---------|
| https://www.frc.org.uk/ | FRC | Регулятор аудита, UK GAAP |
| https://www.gov.uk/companies-house | Companies House | Реестр компаний UK |
| https://www.gov.uk/hmrc | HMRC | Налоговое законодательство UK |
| https://www.fca.org.uk/ | FCA | Регулирование финрынков |

**Частота:** Reference (при обновлениях)

---

## 6. EU & International Law

| URL | Организация | Контент |
|-----|-------------|---------|
| https://eur-lex.europa.eu/ | EUR-Lex | Законодательство ЕС |
| https://www.esma.europa.eu/ | ESMA | Регулятор рынков ЕС |
| https://digital-strategy.ec.europa.eu/ | EC | Регулирование ИИ |
| https://www.oecd.org/ | OECD | Корпоративное управление, BEPS |

**Частота:** Reference (при обновлениях)

---

## 7. AI & Tech Law

| URL | Организация | Контент |
|-----|-------------|---------|
| https://www.nist.gov/ | NIST | AI Risk Management Framework |
| https://www.europarl.europa.eu/ | EU Parliament | EU AI Act |
| https://www2.deloitte.com/insights | Deloitte | Tech & AI insights |
| https://www.pwc.com/ | PwC | Emerging Tech |
| https://www.ey.com/ | EY | Insights |
| https://kpmg.com/ | KPMG | Insights |
| https://law.stanford.edu/codex | Stanford CodeX | Legal Informatics |
| https://cyber.harvard.edu/ | Harvard Berkman | Cyber law |
| https://www.ieee.org/ | IEEE | Стандарты этики ИИ |
| https://www.iso.org/ | ISO | ISO 27001, AI Governance |

**Частота:**
- Big4 Insights: Dynamic (еженедельно)
- Standards: Reference

---

## 8. Uzbekistan Context

| URL | Организация | Контент |
|-----|-------------|---------|
| https://spot.uz/ | Spot | Деловые новости, экономика |
| https://buxgalter.uz/ | Buxgalter | Налоги, отчётность |
| https://uz.kursiv.media/ | Kursiv UZ | Финансы, банкинг |
| https://soliq.uz/ | Налоговый комитет | Налоговый кодекс |

**Частота:**
- spot.uz: Dynamic (ежедневно)
- soliq.uz: Reference (при обновлениях)

**Примечание:** lex.uz и norma.uz → через API, не краулеры

---

## Implementation Notes

### PDF Parsing
```python
# Рекомендуемые инструменты
from unstructured.partition.pdf import partition_pdf  # Сложные документы
from llama_parse import LlamaParse  # Таблицы финотчётов
```

### Link Preservation (lex.uz)
```python
# Критично сохранять:
{
    "document_id": "...",
    "title": "...",
    "status": "active|amended|repealed",
    "amends": ["doc_id_1", "doc_id_2"],
    "amended_by": ["doc_id_3"],
    "repealed_by": "doc_id_4"
}
```

### Frequency Matrix

| Type | Frequency | Examples |
|------|-----------|----------|
| **Dynamic** | Daily/Weekly | spot.uz, Big4 insights, OFAC |
| **Reference** | On update | IFRS, ISA, lex.uz |
| **Static** | Once | Historical documents |

---

## ETL Pipeline Status

| Source | Parser | Status |
|--------|--------|--------|
| IFRS/IAASB | PDF | 📋 Planned |
| SEC EDGAR | HTML/XML | 📋 Planned |
| lex.uz | API | 📋 Planned |
| spot.uz | HTML | 📋 Planned |
| Big4 sites | Mixed | 📋 Planned |

---

## Related Docs

- [Data Circuits](./03_Data_Circuits.md) — Общая архитектура
- [Knowledge Base Structure](../knowledge-base/01_Structure.md) — Блоки A-F
