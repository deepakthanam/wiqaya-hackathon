# Translation review notes

All non-English templates (`ar`, `ur`, `hi`, `ml`, `tl`) are **machine drafts** (`review_status: machine_draft`)
and must be reviewed by a native speaker before any real use. Each template carries an `english_gloss`
back-translation so reviewers can compare it with the English source. The notes below list what to check first.

## Arabic (ar)
- Patients are addressed in the respectful plural, which avoids choosing a gender. CHW scripts address the worker in the masculine singular. Check this suits UAE practice, especially for cervical and breast messages.
- Terms to check:
  - "فحص الأمعاء" for bowel screening ("فحص القولون" may be more familiar)
  - "عدة فحص منزلية" (home test kit)
  - "الماموجرام" (mammogram)
  - "مسحة عنق الرحم" (smear test)
  - "العيادة المتنقلة المجانية" (free health van)
- Blocklist terms "خطر", "نتيجة" and "خجل" are short. They are safe for the current texts but could catch innocent words after edits.

## Urdu (ur)
- The caller speaks in the male form in call scripts. Cervical and breast scripts use the female form. Real callers may need both versions.
- Terms to check: "سروائیکل اسکریننگ", "پیپ سمیئر ٹیسٹ", "آنتوں کی اسکریننگ", "نشوونما" (may be above a 6th-grade reading level) and "یاد دہانیاں".
- Short words were left out of the blocklist because they would match innocent words. For example "مرض" would match "مرضی", and "ابو" would match "ابوظبی".

## Hindi (hi)
- Terms to check:
  - "आंत की स्क्रीनिंग" (bowel screening)
  - "सर्वाइकल स्क्रीनिंग (पैप स्मीयर टेस्ट)"
  - "दिल की सेहत की जांच" (heart-health check)
- Gender: call scripts give both forms (रहा/रही). Recipients are addressed with the masculine or plural "चाहते", except in cervical and breast templates.
- The cascade blocklist blocks "माँ", "भाई" and "पिता". This means cascade texts cannot say "माता-पिता" (parents).

## Malayalam (ml)
- SMS texts are heavily shortened to fit 70 characters per segment. Check that the clipped wording still sounds natural.
- Suffixes after placeholders ("-ന്", "-ന്റെ") may read oddly after some names.
- Terms to check: "ഗർഭാശയമുഖ സ്ക്രീനിംഗ്" (cervical screening) and "കുടൽ സ്ക്രീനിംഗ്" (bowel screening).

## Tagalog (tl)
- Medical terms are left in English (Taglish), e.g. "blood sugar check", "Pap smear", "mammogram". Check they read naturally.
- Short family words ("ama", "ina", "ate", "kuya") are blocked only in cascade messages.

## Known language gap
Bangladeshi residents whose preferred language is Bengali (`bn`) get English messages. The library has no Bengali templates yet. This shows up as a language mismatch in the equity console.
