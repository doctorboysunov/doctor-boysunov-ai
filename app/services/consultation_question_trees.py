"""Dynamic question trees per complaint category — one question at a time."""

from __future__ import annotations

from app.domain.consultation import ComplaintCategory, ConsultationQuestion

_COMMON_ONSET = ConsultationQuestion(
    id="onset",
    text="Shikoyatingiz qachondan boshlangan?",
    required=True,
    order=10,
)
_COMMON_SEVERITY = ConsultationQuestion(
    id="severity",
    text="Og'riq yoki bezovtilik kuchini 1 dan 10 gacha baholang (10 — eng kuchli).",
    required=True,
    order=20,
)
_COMMON_PROGRESSION = ConsultationQuestion(
    id="progression",
    text="Holat yaxshilanayaptimi, yomonlashayaptimi yoki o'zgarmayaptimi?",
    required=True,
    order=30,
)
_COMMON_PRIOR_TREATMENT = ConsultationQuestion(
    id="prior_treatment",
    text="Oldin qanday davolash yoki dori qabul qilganingiz bormi?",
    required=False,
    order=90,
)
_COMMON_CHRONIC = ConsultationQuestion(
    id="chronic_conditions",
    text="Surunkali kasalliklaringiz (qon bosimi, diabet, yurak kasalligi va h.k.) bormi?",
    required=False,
    order=95,
)

_HEADACHE_TREE: tuple[ConsultationQuestion, ...] = (
    _COMMON_ONSET,
    ConsultationQuestion(
        id="headache_location",
        text="Bosh og'rig'i qayerda — peshona, chakka, ensa yoki butun boshdami?",
        required=True,
        order=11,
    ),
    _COMMON_SEVERITY,
    ConsultationQuestion(
        id="headache_character",
        text="Og'riq qanday — bosuvchi, uruvchi, yorilib ketayotgandek yoki boshqa?",
        required=True,
        order=21,
    ),
    ConsultationQuestion(
        id="headache_associated",
        text="Ko'ngil aynishi, qayt qilish, yorug'lik/yovvoyi ovozdan qo'rqish yoki ko'rish buzilishi bormi?",
        required=True,
        order=31,
        red_flag_patterns=(
            r"ko['']?rish",
            r"vision",
            r"nutq",
            r"qo['']?l",
            r"oyoq",
            r"eng kuchli",
            r"birdan",
        ),
        red_flag_label="bosh og'rig'i bilan nevrologik belgilar",
    ),
    _COMMON_PROGRESSION,
    ConsultationQuestion(
        id="headache_triggers",
        text="Stress, uyqusizlik yoki ovqatdan keyin kuchayadimi?",
        required=False,
        order=40,
    ),
    _COMMON_PRIOR_TREATMENT,
)

_LOW_BACK_TREE: tuple[ConsultationQuestion, ...] = (
    _COMMON_ONSET,
    ConsultationQuestion(
        id="back_location",
        text="Og'riq faqat beldami yoki oyoqqa tarqaladimi?",
        required=True,
        order=11,
    ),
    _COMMON_SEVERITY,
    ConsultationQuestion(
        id="back_leg_symptoms",
        text="Oyoqda uvish, kuchsizlik yoki sezgi pasayishi bormi?",
        required=True,
        order=21,
        red_flag_patterns=(r"uvish", r"kuchsiz", r"sezgi", r"ikki\s*oyoq", r"numb", r"weak"),
        red_flag_label="bel og'rig'i bilan nevrologik belgilar",
    ),
    ConsultationQuestion(
        id="back_bladder_bowel",
        text="Siydik yoki axlat tutishda muammo paydo bo'ldimi?",
        required=True,
        order=22,
        red_flag_patterns=(r"ha", r"bor", r"muammo", r"tutolmay", r"inkontinen"),
        red_flag_label="siydik/axlat nazorati buzilishi",
    ),
    ConsultationQuestion(
        id="back_injury",
        text="Jarohat, qulash yoki og'ir yuk ko'tarishdan keyin boshlandimi?",
        required=True,
        order=31,
    ),
    _COMMON_PROGRESSION,
    _COMMON_PRIOR_TREATMENT,
)

_NECK_TREE: tuple[ConsultationQuestion, ...] = (
    _COMMON_ONSET,
    ConsultationQuestion(
        id="neck_location",
        text="Bo'yin og'rig'i qaysi tomonda yoki har ikki tomondami?",
        required=True,
        order=11,
    ),
    _COMMON_SEVERITY,
    ConsultationQuestion(
        id="neck_radiation",
        text="Og'riq yelka, qo'l yoki boshga tarqaladimi?",
        required=True,
        order=21,
    ),
    ConsultationQuestion(
        id="neck_stiffness",
        text="Bo'yin qotishi, isitma yoki bosh og'rig'i ham bormi?",
        required=True,
        order=31,
        red_flag_patterns=(r"isitma", r"qotish", r"fever", r"stiff"),
        red_flag_label="bo'yin qotishi yoki isitma",
    ),
    _COMMON_PROGRESSION,
    _COMMON_PRIOR_TREATMENT,
)

_VERTIGO_TREE: tuple[ConsultationQuestion, ...] = (
    _COMMON_ONSET,
    ConsultationQuestion(
        id="vertigo_type",
        text="Bosh aylanishi harakat bilan kuchayadimi yoki doimiy qoladimi?",
        required=True,
        order=11,
    ),
    ConsultationQuestion(
        id="vertigo_associated",
        text="Qayt qilish, eshitish pasayishi yoki quloq shovqini bormi?",
        required=True,
        order=21,
    ),
    ConsultationQuestion(
        id="vertigo_neuro",
        text="Nutq buzilishi, yurish qiyinligi yoki ko'rish o'zgarishi bormi?",
        required=True,
        order=31,
        red_flag_patterns=(r"nutq", r"yurish", r"ko['']?rish", r"qo['']?l", r"oyoq"),
        red_flag_label="bosh aylanishi bilan nevrologik belgilar",
    ),
    _COMMON_SEVERITY,
    _COMMON_PROGRESSION,
)

_STROKE_TREE: tuple[ConsultationQuestion, ...] = (
    ConsultationQuestion(
        id="stroke_onset",
        text="Belgilar qachon va qanday tezlikda boshlandi?",
        required=True,
        order=5,
        red_flag_patterns=(r"soat", r"daqiq", r"birdan", r"hozir", r"bugun"),
        red_flag_label="o'tkir insult belgilari",
    ),
    ConsultationQuestion(
        id="stroke_face",
        text="Yuzning bir tomoni qiyshaydimi yoki pastga tushdimi?",
        required=True,
        order=10,
        red_flag_patterns=(r"ha", r"bor", r"qiysh", r"tush"),
        red_flag_label="yuz qiyshishi",
    ),
    ConsultationQuestion(
        id="stroke_arm",
        text="Qo'l yoki oyoqda kuchsizlik, uvish yoki harakat qiyinligi bormi?",
        required=True,
        order=11,
        red_flag_patterns=(r"ha", r"bor", r"kuchsiz", r"uvish"),
        red_flag_label="ekstremite kuchsizligi",
    ),
    ConsultationQuestion(
        id="stroke_speech",
        text="Nutq buzilgan, tushunarsiz yoki og'iz burchagi tushganmi?",
        required=True,
        order=12,
        red_flag_patterns=(r"ha", r"bor", r"buzil", r"tush"),
        red_flag_label="nutq buzilishi",
    ),
    ConsultationQuestion(
        id="stroke_consciousness",
        text="Hushdan ketish, chalkashlik yoki kuchli bosh og'rig'i bo'ldimi?",
        required=True,
        order=13,
        red_flag_patterns=(r"ha", r"bor", r"hush", r"chalkash"),
        red_flag_label="hush buzilishi",
    ),
)

_NEUROPATHY_TREE: tuple[ConsultationQuestion, ...] = (
    _COMMON_ONSET,
    ConsultationQuestion(
        id="neuro_location",
        text="Uvish yoki og'riq qayerda — qo'llarda, oyoqlarda yoki ikkalasida?",
        required=True,
        order=11,
    ),
    ConsultationQuestion(
        id="neuro_pattern",
        text="Kechasi kuchayadimi yoki yurishda og'riq bormi?",
        required=True,
        order=21,
    ),
    _COMMON_SEVERITY,
    ConsultationQuestion(
        id="neuro_weakness",
        text="Kuchsizlik ham bormi yoki faqat uvish/sezgi buzilishi?",
        required=True,
        order=31,
        red_flag_patterns=(r"kuchsiz", r"tez\s*tarqal", r"ikki\s*tomon", r"weak"),
        red_flag_label="tez tarqaluvchi kuchsizlik",
    ),
    _COMMON_PROGRESSION,
    _COMMON_CHRONIC,
)

_FACIAL_PALSY_TREE: tuple[ConsultationQuestion, ...] = (
    _COMMON_ONSET,
    ConsultationQuestion(
        id="facial_side",
        text="Yuzning qaysi tomoni ta'sirlangan?",
        required=True,
        order=11,
    ),
    ConsultationQuestion(
        id="facial_eye",
        text="Ko'z yopish yoki qovurg'a ko'tarish qiyinlashdimi?",
        required=True,
        order=21,
    ),
    ConsultationQuestion(
        id="facial_other",
        text="Qo'l-oyoq kuchsizligi, nutq buzilishi yoki bosh og'rig'i ham bormi?",
        required=True,
        order=31,
        red_flag_patterns=(r"ha", r"bor", r"nutq", r"qo['']?l", r"bosh"),
        red_flag_label="yuz falaji bilan qo'shimcha nevrologik belgilar",
    ),
    _COMMON_PROGRESSION,
)

_TREMOR_TREE: tuple[ConsultationQuestion, ...] = (
    _COMMON_ONSET,
    ConsultationQuestion(
        id="tremor_location",
        text="Titroq qayerda — qo'l, bosh yoki butun tanada?",
        required=True,
        order=11,
    ),
    ConsultationQuestion(
        id="tremor_rest",
        text="Dam olayotganda kuchayadimi yoki harakatda kamayadimi?",
        required=True,
        order=21,
    ),
    _COMMON_SEVERITY,
    ConsultationQuestion(
        id="tremor_associated",
        text="Yurish sekinlashishi, nutq pastlashishi yoki muvozanat buzilishi bormi?",
        required=False,
        order=31,
    ),
    _COMMON_PROGRESSION,
)

_MEMORY_TREE: tuple[ConsultationQuestion, ...] = (
    _COMMON_ONSET,
    ConsultationQuestion(
        id="memory_type",
        text="Yaqinda bo'lgan voqealarni unutasizmi yoki eski xotiralar ham buzilyaptimi?",
        required=True,
        order=11,
    ),
    ConsultationQuestion(
        id="memory_daily",
        text="Kundalik ishlar (pul, dori, yo'l topish) qiyinlashdimi?",
        required=True,
        order=21,
    ),
    ConsultationQuestion(
        id="memory_neuro",
        text="Nutq, yurish yoki xulq-atvor o'zgarishi bormi?",
        required=True,
        order=31,
        red_flag_patterns=(r"ha", r"bor", r"tez", r"birdan"),
        red_flag_label="tez rivojlanuvchi kognitiv buzilish",
    ),
    _COMMON_PROGRESSION,
    _COMMON_CHRONIC,
)

_SLEEP_TREE: tuple[ConsultationQuestion, ...] = (
    _COMMON_ONSET,
    ConsultationQuestion(
        id="sleep_type",
        text="Uyquga ketish qiyinmi, tez-tez uyg'onasizmi yoki ertalab charchagan uyg'onasizmi?",
        required=True,
        order=11,
    ),
    ConsultationQuestion(
        id="sleep_snoring",
        text="Xurillash, nafas to'xtashi yoki kunduzgi uyquchanlik bormi?",
        required=True,
        order=21,
    ),
    _COMMON_SEVERITY,
    ConsultationQuestion(
        id="sleep_mood",
        text="Kayfiyat pasayishi yoki xavotir ham kuzatiladimi?",
        required=False,
        order=31,
    ),
    _COMMON_PROGRESSION,
)

_ANXIETY_TREE: tuple[ConsultationQuestion, ...] = (
    _COMMON_ONSET,
    ConsultationQuestion(
        id="anxiety_triggers",
        text="Xavotir qachon kuchayadi — kechasi, odamlar oldida yoki sababsiz?",
        required=True,
        order=11,
    ),
    ConsultationQuestion(
        id="anxiety_physical",
        text="Yurak urishi, nafas qisilishi yoki ko'krak og'rig'i ham bo'ladimi?",
        required=True,
        order=21,
        red_flag_patterns=(r"ko['']?krak", r"nafas", r"og['']?riq"),
        red_flag_label="jismoniy xavf belgilari",
    ),
    _COMMON_SEVERITY,
    ConsultationQuestion(
        id="anxiety_sleep",
        text="Uyqu va ishtaha qanday?",
        required=False,
        order=31,
    ),
    _COMMON_PROGRESSION,
)

_DEPRESSION_TREE: tuple[ConsultationQuestion, ...] = (
    _COMMON_ONSET,
    ConsultationQuestion(
        id="depression_mood",
        text="Kayfiyat pasayishi qancha vaqt davom etmoqda?",
        required=True,
        order=11,
    ),
    ConsultationQuestion(
        id="depression_interest",
        text="Ilgari yoqtirgan mashg'ulotlaringizga qiziqish kamaydimi?",
        required=True,
        order=21,
    ),
    ConsultationQuestion(
        id="depression_safety",
        text="O'zingizga yoki boshqalarga zarar berish haqida fikrlar bo'ladimi?",
        required=True,
        order=31,
        red_flag_patterns=(r"ha", r"bor", r"o['']?zimni", r"jon", r"suicid"),
        red_flag_label="o'z joniga qasd xavfi",
    ),
    _COMMON_SEVERITY,
    _COMMON_PROGRESSION,
)

_OTHER_TREE: tuple[ConsultationQuestion, ...] = (
    _COMMON_ONSET,
    ConsultationQuestion(
        id="other_description",
        text="Shikoyatingizni batafsilroq tasvirlab bering.",
        required=True,
        order=11,
    ),
    _COMMON_SEVERITY,
    ConsultationQuestion(
        id="other_neuro_signs",
        text="Kuchsizlik, uvish, nutq buzilishi yoki hush buzilishi bormi?",
        required=True,
        order=21,
        red_flag_patterns=(r"ha", r"bor", r"kuchsiz", r"uvish", r"nutq", r"hush"),
        red_flag_label="nevrologik qizil bayroqlar",
    ),
    _COMMON_PROGRESSION,
    _COMMON_PRIOR_TREATMENT,
)

QUESTION_TREES: dict[ComplaintCategory, tuple[ConsultationQuestion, ...]] = {
    "headache": _HEADACHE_TREE,
    "low_back_pain": _LOW_BACK_TREE,
    "neck_pain": _NECK_TREE,
    "vertigo": _VERTIGO_TREE,
    "stroke": _STROKE_TREE,
    "neuropathy": _NEUROPATHY_TREE,
    "facial_nerve_palsy": _FACIAL_PALSY_TREE,
    "tremor": _TREMOR_TREE,
    "memory_problems": _MEMORY_TREE,
    "sleep_disorders": _SLEEP_TREE,
    "anxiety": _ANXIETY_TREE,
    "depression": _DEPRESSION_TREE,
    "other_neurological": _OTHER_TREE,
}


def get_questions_for_category(category: ComplaintCategory) -> tuple[ConsultationQuestion, ...]:
    return QUESTION_TREES.get(category, _OTHER_TREE)


def get_question_by_id(category: ComplaintCategory, question_id: str) -> ConsultationQuestion | None:
    for question in get_questions_for_category(category):
        if question.id == question_id:
            return question
    return None


def select_next_question(
    category: ComplaintCategory,
    asked_ids: set[str],
    answers: dict[str, str],
) -> ConsultationQuestion | None:
    tree = get_questions_for_category(category)
    unanswered = [q for q in tree if q.id not in asked_ids]
    if not unanswered:
        return None

    required_pending = [q for q in unanswered if q.required]
    if required_pending:
        return sorted(required_pending, key=lambda item: item.order)[0]

    optional_pending = [q for q in unanswered if not q.required]
    if optional_pending:
        return sorted(optional_pending, key=lambda item: item.order)[0]
    return None


def has_enough_information(
    category: ComplaintCategory,
    asked_ids: set[str],
    answers: dict[str, str],
) -> bool:
    tree = get_questions_for_category(category)
    required = [q for q in tree if q.required]
    answered_required = sum(1 for q in required if q.id in answers and answers[q.id].strip())
    if answered_required >= len(required):
        return True
    if answered_required >= max(3, len(required) - 1) and len(answers) >= 4:
        return True
    return False
