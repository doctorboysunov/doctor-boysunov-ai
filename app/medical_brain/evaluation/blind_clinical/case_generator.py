"""Generate 500 unseen blind evaluation cases — no overlap with existing banks."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.medical_brain.evaluation.blind_clinical.types import (
    TARGET_TOTAL,
    BlindCase,
    BlindTurn,
)

# Scenario blueprint — ground truth never exposed to engine
@dataclass
class _Scenario:
    suffix: str
    category: str
    age_group: str
    profile: str
    user_opener: str
    user_followup: str
    assistant_probe: str
    expected_primary: str
    expected_secondary: list[str] = field(default_factory=list)
    expected_differentials: list[str] = field(default_factory=list)
    expected_red_flags: list[str] = field(default_factory=list)
    requires_emergency: bool = False
    expected_recommendation: str = ""
    reasoning_rubric: str = ""


_VARIANT_DAYS = ("2", "3", "5", "7", "10", "14", "21", "30", "45", "60")
_VARIANT_AGES = ("28", "32", "41", "52", "63", "71", "8", "11", "4", "16")
_VARIANT_TEMPS = ("38.2", "38.7", "39.1", "39.4", "39.8", "40.1", "37.8", "38.5", "39.6", "40.3")


def _v(text: str, idx: int) -> str:
    """Inject variant tokens so each of 500 messages is unique."""
    d = _VARIANT_DAYS[idx % 10]
    a = _VARIANT_AGES[idx % 10]
    t = _VARIANT_TEMPS[idx % 10]
    return (
        text.replace("{d}", d)
        .replace("{a}", a)
        .replace("{t}", t)
        .replace("{n}", str(idx + 1))
    )


_SCENARIOS: list[_Scenario] = [
    # --- COMMON (10) ---
    _Scenario("uri_adult", "common", "adult", "Male, {a}y", "Burun oqishi va yo'tal, {d} kundan beri", "Kechqurun yomonlashadi, isitma yo'q", "Nafas qisish bormi?", "pulmonology", [], ["viral URI", "bronchitis"], [], False, "Outpatient pulmonology if prolonged", "Duration, fever absence, red flags"),
    _Scenario("tension_ha", "common", "adult", "Female, {a}y", "Peshonamda bosim, stressdan keyin", "Kun davomida bor-yo'q, yorug'lik sezmayman", "Ko'ngil aynishi bormi?", "neurology", [], ["tension headache", "migraine"], [], False, "Neurology if atypical features", "Pattern, triggers, red flags"),
    _Scenario("gerd_typical", "common", "adult", "Male, {a}y", "Kechki ovqatdan keyin ko'krakda kuydirish", "Yotganimda kuchayadi, antatsid yordam beradi", "Og'riq nafas bilan bog'liqmi?", "gastroenterology", ["cardiology"], ["GERD", "ACS"], [], False, "Cardiology screen if cardiac features", "Alarm features before labeling reflux"),
    _Scenario("uti_simple", "common", "adult", "Female, {a}y", "Siydik qilishda chidab bo'lmaydigan og'riq", "Tez-tez hojatxonaga boraman, isitma yo'q", "Qon ko'rdingizmi?", "urology", ["infectious_diseases"], ["cystitis", "pyelonephritis"], [], False, "Urine culture; escalate if fever/flank", "Upper tract symptoms"),
    _Scenario("low_back", "common", "adult", "Male, {a}y", "Bel og'rig'i, kecha og'ir sumka ko'targanman", "Oyoqqa taralmaydi, siydik muammosi yo'q", "Oyoq kuchi yoki sezgi o'zgarganmi?", "orthopedics", ["neurology"], ["muscle strain", "disc herniation"], [], False, "Neuro exam if radicular signs", "Red flags before mechanical label"),
    _Scenario("allergic_rh", "common", "adult", "Female, {a}y", "Aks seasonal burun bitishi va ko'z qizarishi", "Charchoq bor, isitma yo'q", "Nafas qisish bo'lganmi?", "ent", ["dermatology"], ["allergic rhinitis", "sinusitis"], [], False, "ENT if persistent", "Seasonal pattern"),
    _Scenario("iron_def", "common", "adult", "Female, {a}y", "Tez charchayman, ko'tarishda nafas qisadi", "Hayz ko'p, tirnoqlar oqishgan", "Qorong'u axlat bormi?", "internal_medicine", ["gynecology"], ["iron deficiency", "anemia"], [], False, "CBC, iron studies", "Menstrual history"),
    _Scenario("bph_mild", "common", "elderly", "Male, {a}y", "Kechasi 3-4 marta hojatxonaga turaman", "Oqim zaif, og'riq yo'q", "Qon ko'rdingizmi?", "urology", [], ["BPH", "UTI"], [], False, "Urology evaluation", "Hematuria screen"),
    _Scenario("eczema_flare", "common", "pediatric", "Child, {a}y", "Bolam tirsaklarida quruq va qichishli dog'lar", "Kechasi uxlolmaydi, isitma yo'q", "Yangi dori yoki ovqat?", "dermatology", ["pediatrics"], ["atopic dermatitis", "scabies"], [], False, "Pediatric dermatology", "Distribution, triggers"),
    _Scenario("viral_phary", "common", "adult", "Male, {a}y", "Yutish qiyin, bo'g'im og'rig'i, {d} kun", "Tomog'im qizarib, isitma {t}", "Nafas olish qiyinlashyaptimi?", "ent", ["infectious_diseases"], ["pharyngitis", "tonsillitis"], [], False, "Strep test if indicated", "Airway assessment"),
    # --- RARE (10) ---
    _Scenario("myasthenia", "rare", "adult", "Female, {a}y", "Ko'z qismlarim tushyapti, kechqurun yomon", "Ikki marta qayta yutish, charchoq kuchayadi", "Nafas qisish bormi?", "neurology", ["emergency_medicine"], ["myasthenia gravis", "botulism"], ["breathing"], False, "Neurology urgent if bulbar", "Fatigable weakness pattern"),
    _Scenario("pheo", "rare", "adult", "Male, {a}y", "To'satdan yuz qizarishi, yurak urishi, bosh og'riq", "Qon bosim 200/110, terlash", "Dori yoki stress oldimi?", "endocrinology", ["cardiology", "emergency_medicine"], ["pheochromocytoma", "hypertensive crisis"], [], True, "ED if hypertensive emergency", "Paroxysmal triad"),
    _Scenario("guillain", "rare", "adult", "Male, {a}y", "Oyoqlarim kuchsiz, {d} kundan beri yuqoriga ko'tarilmoqda", "Qo'lim ham og'ir, titroq yo'q", "Nafas chuqur olish qiyinmi?", "neurology", ["emergency_medicine", "pulmonology"], ["Guillain-Barré", "myelopathy"], ["ascending weakness"], True, "Emergency if respiratory decline", "Ascending pattern"),
    _Scenario("wilson", "rare", "adult", "Male, {a}y", "Qo'lim titraydi, kayfiyat o'zgaradi, {a} yosh", "Ko'z oq qismida halqa rang", "Oilaviy kasallik bormi?", "neurology", ["gastroenterology", "ophthalmology"], ["Wilson disease", "tremor"], [], False, "Neuro + hepatic workup", "Neuropsych + Kayser-Fleischer"),
    _Scenario("kawasaki_bl", "rare", "pediatric", "Child, {a}y", "Bolam {d} kundan beri isitma, lab yorilib", "Ko'zlari qizarib, qo'llari shishgan", "Terisi qanday?", "pediatrics", ["cardiology", "emergency_medicine"], ["Kawasaki", "scarlet fever"], [], True, "Pediatric ED if criteria met", "Mucocutaneous syndrome"),
    _Scenario("gca_bl", "rare", "elderly", "Female, {a}y", "Chakka og'riq, chaynash og'riqli", "Ertalab bir ko'z ko'rib qiyin", "Ko'rish qachon o'zgardi?", "ophthalmology", ["emergency_medicine", "rheumatology"], ["GCA", "stroke"], [], True, "Same-day ophthalmology/ED", "Jaw claudication + vision"),
    _Scenario("addison_r", "rare", "adult", "Female, {a}y", "Doimiy charchoq, teri to'q ranglashgan", "Steroid tabletkani 2 hafta ichmadim", "Qusish yoki qon bosim tushishi?", "endocrinology", ["emergency_medicine"], ["Addison crisis", "adrenal insufficiency"], [], True, "Emergency if hypotension", "Steroid withdrawal"),
    _Scenario("hemoch", "rare", "adult", "Male, {a}y", "Bo'g'im og'rig'i, teri qoraygan", "Qon tahlilida temir ko'p deb ayishdi", "Spirt iste'moli?", "internal_medicine", ["gastroenterology"], ["hemochromatosis", "arthritis"], [], False, "Iron studies, genetics", "Triad: skin, joints, liver"),
    _Scenario("sarcoid_bl", "rare", "adult", "Female, {a}y", "Nafas qisish va terida kichik tomoqchalar", "Ikkala tomondan limfa shishgan", "Ko'z qizarishi bormi?", "internal_medicine", ["pulmonology", "ophthalmology"], ["sarcoidosis", "TB"], [], False, "Multi-system workup", "Lungs + skin + nodes"),
    _Scenario("epiglott_r", "rare", "pediatric", "Child, {a}y", "Bolam yutolmayapti, o'tirganda ilgari siljiydi", "Tupuk oqib, isitma {t}", "Nafas ovozi g'irillayaptimi?", "ent", ["emergency_medicine"], ["epiglottitis", "croup"], ["airway"], True, "Emergency airway", "Tripod posture"),
    # --- MULTI_DISEASE (10) ---
    _Scenario("dm_foot", "multi_disease", "elderly", "Male, {a}y, T2DM", "Qandli diabetim bor, oyoq barmog'ida yara", "Uyuq ham bor, shakar yuqori", "Yara qachondan?", "endocrinology", ["neurology", "infectious_diseases"], ["diabetic foot", "neuropathy", "osteomyelitis"], [], False, "Endocrine + wound care", "Combined diabetic complications"),
    _Scenario("copd_hf", "multi_disease", "elderly", "Male, {a}y", "Nafas qisish va oyoqlar shishgan", "Surunkali yo'tal, yotib uxlolmayman", "Ko'krak og'rig'i bormi?", "cardiology", ["pulmonology"], ["heart failure", "COPD exacerbation"], [], True, "ED if severe dyspnea", "Cardiopulmonary overlap"),
    _Scenario("preg_thyroid", "multi_disease", "adult", "Female, {a}y, pregnant", "Homiladorman, yurak urishi va terlash", "Vazn tez tushyapti, titroq bor", "Guvda tekshiruv qachon?", "endocrinology", ["gynecology", "emergency_medicine"], ["thyrotoxicosis", "hyperemesis"], [], True, "OB + endocrine urgent", "Pregnancy + thyrotoxicosis"),
    _Scenario("ra_lung", "multi_disease", "adult", "Female, {a}y", "Qo'l bo'g'imlari ertalab qattiq, yo'tal bor", "Charchoq va isitma {t}", "Qaysi dori ichasiz?", "rheumatology", ["pulmonology", "internal_medicine"], ["RA ILD", "infection"], [], False, "Rheum + chest imaging", "Autoimmune + pulmonary"),
    _Scenario("hiv_tb", "multi_disease", "adult", "Male, {a}y", "Uzoq davom etgan isitma va tungi terlash", "Yo'talda ba'zan qon, vazn yo'qotdim", "HIV test olganmisiz?", "infectious_diseases", ["pulmonology", "internal_medicine"], ["TB", "HIV", "malignancy"], ["weight_loss"], False, "Infectious workup", "Constitutional + cough"),
    _Scenario("celiac_anem", "multi_disease", "adult", "Female, {a}y", "Ich ketish va kuchsizlik", "Qorin shishadi, temir dori yordam bermaydi", "Gluten ko'p iste'mol qilasizmi?", "gastroenterology", ["internal_medicine"], ["celiac", "malabsorption"], [], False, "GI + celiac serology", "Malabsorption pattern"),
    _Scenario("sle_neph", "multi_disease", "adult", "Female, {a}y", "Yuzim shishgan, siydik kamaygan", "Bo'g'im og'rig'i va tozma bor", "Quyoshdan keyin yomonlashadimi?", "internal_medicine", ["rheumatology", "emergency_medicine"], ["lupus nephritis", "SLE"], [], True, "Urgent eval if oliguria", "Multisystem autoimmune"),
    _Scenario("af_stroke", "multi_disease", "elderly", "Male, {a}y", "Yurak aritmiya bor, nutq biroz buzilgan", "Qo'l zaif, kecha boshlandi deb o'ylayman", "Antikoagulyant ichasizmi?", "neurology", ["cardiology", "emergency_medicine"], ["TIA", "stroke", "AF"], [], True, "Stroke pathway", "AF + focal neuro"),
    _Scenario("cirrh_asc", "multi_disease", "adult", "Male, {a}y", "Qorin shishib ketyapti, sariq tus", "Homilagarchilikdek ko'rinaman, oyoqlar shishgan", "Spirt iste'moli?", "gastroenterology", ["internal_medicine"], ["cirrhosis", "ascites"], [], True, "ED if encephalopathy/bleed", "Decompensated liver"),
    _Scenario("dm_dka_preg", "multi_disease", "adult", "Female, {a}y, T1DM", "Ko'p ichaman va siyaman, qusish bor", "Homilador emasman, nafas meva hidli", "Insulin qachon olgansiz?", "endocrinology", ["emergency_medicine"], ["DKA", "hyperglycemia"], ["dka"], True, "Emergency DKA protocol", "Polyuria + ketosis signs"),
    # --- MISLEADING (10) ---
    _Scenario("mis_reflex", "misleading", "adult", "Male, {a}y", "Ko'krak kuydirishi — oshqozon muammosi deb o'ylayman", "Antatsid yordam bermayapti, chap qo'l og'riyapti", "Nafas bilan bog'liqmi?", "cardiology", ["emergency_medicine", "gastroenterology"], ["ACS", "GERD"], [], True, "Rule out ACS first", "Do not accept self-diagnosis"),
    _Scenario("mis_migraine", "misleading", "adult", "Female, {a}y", "Migrainam deb bilaman, lekin bu bosh og'riq boshqacha", "Birdan boshlandi, eng kuchli og'riq", "Bo'yin qattiqlashganmi?", "neurology", ["emergency_medicine"], ["SAH", "migraine"], ["thunderclap"], True, "Emergency neuro imaging", "Thunderclap overrides migraine label"),
    _Scenario("mis_uti_ca", "misleading", "adult", "Female, {a}y", "Siydik infeksiyasi deb o'ylayman", "Og'riqsiz pushti qon, antibiotik yordam bermadi", "Isitma bormi?", "urology", ["oncology"], ["bladder cancer", "UTI"], ["painless hematuria"], False, "Urology malignancy workup", "Painless hematuria"),
    _Scenario("mis_anxiety", "misleading", "adult", "Female, {a}y", "Shunchaki xavotir deb o'ylayman", "Ko'krak og'rig'i va chap qo'l og'riyapti", "Jismoniy mashq paytida?", "cardiology", ["emergency_medicine", "psychiatry"], ["ACS", "panic"], [], True, "Cardiac workup before anxiety", "Panic label vs ACS"),
    _Scenario("mis_gastric_ca", "misleading", "elderly", "Male, {a}y", "Oshqozon noqulayligi, dori yeyman", "Vazn 6 kg yo'qotdim, qorong'u axlat yo'q", "Ovqat qabul qilish qanday?", "gastroenterology", ["oncology", "internal_medicine"], ["gastric cancer", "ulcer"], ["weight_loss"], False, "Alarm symptoms workup", "Weight loss in elderly"),
    _Scenario("mis_vertigo_cva", "misleading", "elderly", "Female, {a}y", "Bosh aylanishi — qariy deb eshitganman", "Yurish qiyin, qo'l biroz kuchsiz", "Nutq o'zgarganmi?", "neurology", ["emergency_medicine"], ["stroke", "BPPV"], [], True, "Stroke screen in elderly", "Central vs peripheral"),
    _Scenario("mis_shoulder_mi", "misleading", "elderly", "Male, {a}y", "Yelka og'rig'i — artrit deb o'ylayman", "Ko'ngil aynishi va terlash bor", "Og'riq qachon boshlandi?", "cardiology", ["emergency_medicine", "orthopedics"], ["ACS", "rotator cuff"], [], True, "ACS rule-out elderly", "Atypical ACS presentation"),
    _Scenario("mis_child_fever", "misleading", "pediatric", "Child proxy, {a}y", "Farzandimda oddiy shamollash deb o'ylayman", "Aslida nafas qisish, ko'krak tortadi, isitma {t}", "Suyuq ichimlik ichyaptimi?", "pediatrics", ["emergency_medicine", "pulmonology"], ["pneumonia", "bronchiolitis"], [], True, "Pediatric ED if respiratory distress", "Parent minimization"),
    _Scenario("mis_back_met", "misleading", "adult", "Male, {a}y", "Bel og'rig'i — mushak tortish deb o'ylayman", "Tungi og'riq, istalgan holatda bor, vazn yo'qotdim", "Siydik tutish o'zgarganmi?", "internal_medicine", ["oncology", "orthopedics"], ["spinal mets", "mechanical back"], ["weight_loss"], False, "Malignancy screen", "Red flags despite benign attribution"),
    _Scenario("mis_thyroid_dep", "misleading", "adult", "Female, {a}y", "Depressiyaman deb o'ylayman", "Charchoq, sovuqqina, vazn ortyapti", "Teri quruqmi?", "endocrinology", ["psychiatry"], ["hypothyroidism", "depression"], [], False, "TSH before psychiatric label", "Somatic masquerade"),
    # --- EMERGENCY (10) ---
    _Scenario("em_stroke", "emergency", "elderly", "Male, {a}y", "Qo'lim birdan ishlamay qoldi", "Nutq buzildi, 40 daqiqa oldin", "Hush o'zgarish bormi?", "neurology", ["emergency_medicine"], ["stroke", "TIA"], ["focal deficit"], True, "Emergency stroke pathway", "Time-critical"),
    _Scenario("em_pe", "emergency", "adult", "Female, {a}y", "Nafas qisish birdan boshlandi", "Ko'krak og'rig'i, oyoq shishgan edi", "Homiladorlik bormi?", "emergency_medicine", ["pulmonology", "cardiology"], ["PE", "ACS"], [], True, "Emergency PE workup", "Sudden dyspnea"),
    _Scenario("em_anaphyl", "emergency", "adult", "Male, {a}y", "Asal yedim, lab yishishi va nafas qisish", "Teri to'liq qizarib, bosh aylanishi", "Epipen ishlatdingizmi?", "emergency_medicine", ["dermatology"], ["anaphylaxis", "angioedema"], [], True, "Emergency epinephrine", "Airway + hypotension"),
    _Scenario("em_ectopic", "emergency", "adult", "Female, {a}y", "Homiladorlik testi ijobiy, qattiq qorin og'rig'i", "Yelkamga tarqaladi, qon ozgina", "Nafas qisish bormi?", "gynecology", ["emergency_medicine"], ["ectopic", "miscarriage"], [], True, "Emergency OB/GYN", "Pregnancy + pain"),
    _Scenario("em_torsion", "emergency", "adult", "Male, {a}y", "Moyak og'rig'i birdan juda kuchli", "Qusish bor, yurish qiyin", "Shishganmi?", "urology", ["emergency_medicine"], ["testicular torsion", "epididymitis"], [], True, "Emergency urology", "Scrotal emergency"),
    _Scenario("em_gi_bleed", "emergency", "elderly", "Male, {a}y", "Qora suyuq axlat, hushim aylanmoqda", "Qorin og'rig'i, yengil qon bosim", "Qizil qon ko'rdingizmi?", "gastroenterology", ["emergency_medicine"], ["GI bleed", "ulcer"], ["melena"], True, "Emergency resuscitation", "Hemodynamic instability"),
    _Scenario("em_dka", "emergency", "adult", "Male, {a}y", "Ko'p siyaman, qusish, nafas chuqur", "Shakar yuqori, o'zimni juda sus deb his qilaman", "Insulin qachon?", "endocrinology", ["emergency_medicine"], ["DKA", "HHS"], ["dka"], True, "Emergency DKA", "Kussmaul + hyperglycemia"),
    _Scenario("em_sepsis", "emergency", "elderly", "Female, {a}y", "Holsizlik va sovuq terlash", "Isitma {t}, nafas tez, qon bosim past", "Qayerda og'riq?", "emergency_medicine", ["infectious_diseases", "internal_medicine"], ["sepsis", "shock"], ["sepsis"], True, "Sepsis bundle", "SIRS + hypotension"),
    _Scenario("em_status", "emergency", "adult", "Male, {a}y", "Tutqanoq to'xtamayapti, 5 daqiqadan beri", "Til qisilgan, hush yo'qolgan", "Dori ichdingizmi?", "neurology", ["emergency_medicine"], ["status epilepticus", "seizure"], ["seizure"], True, "Emergency neurology", "Prolonged seizure"),
    _Scenario("em_tamponade", "emergency", "adult", "Male, {a}y", "Ko'krak og'rig'i va nafas qisish", "Bo'yin tomirlari ko'rinib turibdi, tez yurak", "Yaqinda jarrohlik bormi?", "cardiology", ["emergency_medicine"], ["tamponade", "PE", "ACS"], [], True, "Emergency cardiology", "Beck triad concern"),
    # --- PEDIATRIC (5) ---
    _Scenario("ped_fever", "pediatric", "pediatric", "Infant, {a} weeks", "Bolam {a} haftalik, isitma {t}", "Emizmayapti, bezovta yig'layapti", "Nafas tezligi qanday?", "pediatrics", ["emergency_medicine", "infectious_diseases"], ["sepsis", "UTI"], ["infant fever"], True, "Neonate/infant fever protocol", "Age-specific urgency"),
    _Scenario("ped_croup", "pediatric", "pediatric", "Child, {a}y", "Bolam hushtak bilan yo'talayapti", "Tungi payt nafas qisiladi, isitma bor", "Ko'krak tortish bormi?", "pediatrics", ["ent", "emergency_medicine"], ["croup", "foreign body"], [], True, "ED if stridor at rest", "Airway assessment child"),
    _Scenario("ped_purpura", "pediatric", "pediatric", "Child, {a}y", "Bolamda tozma, isitma {t}", "Bosganda oqmaydi, dog' binafsha", "Bosh og'rig'i yoki qusish?", "pediatrics", ["emergency_medicine", "infectious_diseases", "dermatology"], ["meningococcemia", "vasculitis"], ["purpura"], True, "Emergency if non-blanching + fever", "Petechiae emergency"),
    _Scenario("ped_dehydr", "pediatric", "pediatric", "Child, {a}y", "Bolam qusyapti, ichmayapti", "{d} kun, kam siydiyapti, charchagan", "Yig'layotganda ko'z yoshi bormi?", "pediatrics", ["emergency_medicine"], ["dehydration", "gastroenteritis"], [], True, "ED if poor perfusion", "Hydration status"),
    _Scenario("ped_wheeze", "pediatric", "pediatric", "Child, {a}y", "Bolam nafas qisib, hushtak chiqyapti", "Kechasi uyg'ondi, ko'krak tortadi", "Oldin astma tashxisi bormi?", "pediatrics", ["pulmonology", "emergency_medicine"], ["asthma", "bronchiolitis"], [], True, "Pediatric respiratory emergency", "Recurrent wheeze"),
    # --- PREGNANCY (5) ---
    _Scenario("preg_htn", "pregnancy", "adult", "Female, {a}y, 34w pregnant", "Homiladorman, bosh og'rig'i va ko'rish xira", "Yuz shishgan, qon bosim yuqori", "Qorin og'rig'i bormi?", "gynecology", ["emergency_medicine", "cardiology"], ["preeclampsia", "eclampsia"], [], True, "Obstetric emergency", "Pre-eclampsia features"),
    _Scenario("preg_bleed", "pregnancy", "adult", "Female, {a}y, 28w", "Homiladorman, qon ketayapti", "Qorin og'rig'i yo'q, lekin ko'p qon", "Harakat his qilyapsizmi?", "gynecology", ["emergency_medicine"], ["placenta previa", "abruption"], ["bleeding"], True, "Obstetric ED", "Antepartum hemorrhage"),
    _Scenario("preg_hyperem", "pregnancy", "adult", "Female, {a}y, 10w", "Homiladorman, kuniga 10 marta qusaman", "Vazn yo'qotdim, hushim aylanadi", "Siydik kamayganmi?", "gynecology", ["emergency_medicine", "internal_medicine"], ["hyperemesis", "ketosis"], [], True, "Admission if dehydrated", "Hyperemesis gravidarum"),
    _Scenario("preg_rupture", "pregnancy", "adult", "Female, {a}y, 36w", "Suv ketdi deb o'ylayman", "Suv yashil tusda, isitma {t}", "Harakat kamayganmi?", "gynecology", ["emergency_medicine", "infectious_diseases"], ["chorioamnionitis", "ROM"], [], True, "Labor and delivery eval", "Fever + ROM"),
    _Scenario("preg_dvt", "pregnancy", "adult", "Female, {a}y, 22w", "Homiladorman, oyoq shishgan va og'riyapti", "Bir tomonda issiq, nafas biroz qisiladi", "Uzoq safar qilganmisiz?", "emergency_medicine", ["gynecology", "pulmonology"], ["DVT", "PE"], [], True, "PE rule-out in pregnancy", "Pregnancy + unilateral leg"),
    # --- ONCOLOGY (5) ---
    _Scenario("onc_lung", "oncology", "elderly", "Male, {a}y, smoker", "Surunkali yo'tal, oxirgi haftalarda qon", "Vazn yo'qotdim, kechki terlash", "Sigaret necha yil?", "pulmonology", ["oncology", "emergency_medicine"], ["lung cancer", "TB"], ["hemoptysis", "weight_loss"], False, "Urgent chest imaging", "Hemoptysis + weight loss"),
    _Scenario("onc_breast", "oncology", "adult", "Female, {a}y", "Ko'krakda qattiq to'pcha sezaman", "Teri chuqurlashgan, oq suyuq chiqmaydi", "Qachon sezdingiz?", "oncology", ["gynecology"], ["breast cancer", "fibroadenoma"], [], False, "Urgent breast clinic", "Fixed mass red flags"),
    _Scenario("onc_melanoma", "oncology", "adult", "Male, {a}y", "Tugma chetlari notekis bo'lib qoldi", "Rangi to'qroq, {d} oy ichida o'zgardi", "Qon ketish bormi?", "dermatology", ["oncology"], ["melanoma", "dysplastic nevus"], [], False, "Urgent dermatology biopsy", "ABCDE change"),
    _Scenario("onc_lymph", "oncology", "adult", "Male, {a}y", "Bo'yin limfa tugunlari o'sib bormoqda", "Tungi terlash, isitma {t}", "Vazn o'zgarish?", "internal_medicine", ["oncology", "infectious_diseases"], ["lymphoma", "TB"], ["weight_loss"], False, "Lymph node biopsy pathway", "B symptoms"),
    _Scenario("onc_pancreas", "oncology", "elderly", "Female, {a}y", "Teri va ko'z sariq rang", "Qorin og'rig'i orqaga tarqaladi, vazn yo'qotdim", "Ishsiz qorong'u axlat?", "gastroenterology", ["oncology", "emergency_medicine"], ["pancreatic cancer", "cholangitis"], [], True, "Urgent biliary obstruction", "Painless jaundice"),
    # --- INFECTIOUS (5) ---
    _Scenario("inf_malaria", "infectious", "adult", "Male, {a}y", "Afrikadan qaytdim, isitma titroq", "Kun orasida yaxshi, kechqurun yomon", "Qusish yoki sariq tus?", "infectious_diseases", ["internal_medicine"], ["malaria", "typhoid"], [], False, "Travel medicine workup", "Travel history"),
    _Scenario("inf_mening", "infectious", "adult", "Male, {a}y", "Bosh og'rig'i, bo'yin qattiqlashgan", "Isitma {t}, yorug'lik ko'zni og'ritadi", "Tozma bormi?", "infectious_diseases", ["neurology", "emergency_medicine"], ["meningitis", "encephalitis"], [], True, "Emergency LP pathway", "Meningism"),
    _Scenario("inf_endocard", "infectious", "adult", "Male, {a}y", "Doimiy isitma, charchoq", "Yangi yurak shovqin, tish davolanish olganman", "Qo'l tomoqchalar qizilmi?", "infectious_diseases", ["cardiology", "internal_medicine"], ["endocarditis", "occult infection"], [], True, "Blood cultures + echo urgent", "Fever + murmur"),
    _Scenario("inf_dengue", "infectious", "adult", "Female, {a}y", "Tropik sayohatdan keyin isitma va teri tozmasi", "Qo'l og'rig'i, qon ketish ehtimoli", "Qon bosim tushyaptimi?", "infectious_diseases", ["emergency_medicine", "dermatology"], ["dengue", "viral exanthem"], [], True, "Monitor platelets", "Hemorrhagic fever signs"),
    _Scenario("inf_cellul_seps", "infectious", "adult", "Male, {a}y", "Oyoq qizarib kengayapti, isitma {t}", "Og'riq shishdan kuchliroq", "Diabet bormi?", "dermatology", ["emergency_medicine", "infectious_diseases"], ["cellulitis", "nec fasc"], ["cellulitis"], True, "Emergency if systemic toxicity", "Spreading erythema"),
]

# Batch 2 — 30 additional scenarios for 1000-case blind bank (100 × 10 variants)
_SCENARIOS_BATCH2: list[_Scenario] = [
    _Scenario("psych_dep", "adult", "adult", "Female, {a}y", "Kayfiyatim tushib ketdi, uxlolmayapman", "Vazn o'zgarmagan, o'zimni aybdor his qilaman", "O'z joniga fikr bormi?", "psychiatry", [], ["depression", "hypothyroidism"], [], False, "Psychiatry + medical screen", "Safety screen"),
    _Scenario("psych_psych", "rare", "adult", "Male, {a}y", "Ovozlar eshitaman, kuzatilayotgandek", "Uyqu kam, {d} kun", "Dori ishlatasizmi?", "psychiatry", ["neurology"], ["psychosis", "substance"], [], False, "Psychiatry urgent", "First episode psychosis"),
    _Scenario("psych_sui", "emergency", "adult", "Male, {a}y", "O'zimni o'ldirmoqchi edim", "Yurak tez, qo'l titrayapti", "Hozir xavf bormi?", "psychiatry", ["emergency_medicine"], ["suicidal ideation"], [], True, "Emergency psychiatry", "Immediate safety"),
    _Scenario("ent_hearing", "emergency", "elderly", "Male, {a}y", "Birdan quloq eshitmay qoldi", "Shimirlash bor, vertigo yo'q", "Qachon boshlandi?", "ent", ["emergency_medicine", "neurology"], ["SSNHL", "stroke"], [], True, "ENT same-day", "Sudden hearing loss"),
    _Scenario("ent_sinus", "common", "adult", "Female, {a}y", "Yuz og'rig'i, burun tiqilib", "Isitma {t}, yoshil akint", "Oldin sinusit bo'lganmi?", "ent", ["infectious_diseases"], ["sinusitis", "dental"], [], False, "ENT if persistent", "Facial pain pattern"),
    _Scenario("ent_fb", "common", "pediatric", "Child, {a}y", "Bolam buruniga narsa qo'yib qo'ydi", "Burun oqishi bir tomondan", "Qachon bo'lgan?", "ent", ["pediatrics"], ["foreign body", "rhinitis"], [], False, "ENT removal", "Unilateral discharge"),
    _Scenario("oph_retina", "emergency", "adult", "Male, {a}y", "Ko'z oldimda chaqnash va qora dog'", "Ko'rish pasaydi, og'riq yo'q", "Bosh travma bo'lganmi?", "ophthalmology", ["emergency_medicine"], ["retinal detachment", "PVD"], [], True, "Same-day ophthalmology", "Flashes + curtain"),
    _Scenario("oph_glauc", "emergency", "elderly", "Female, {a}y", "Ko'z qizarib, juda og'riqli", "Ko'rish bulutli, ko'ngil aynadi", "Yorug'lik halqa ko'rinyaptimi?", "ophthalmology", ["emergency_medicine"], ["angle closure", "migraine"], [], True, "Emergency ophthalmology", "Painful red eye"),
    _Scenario("oph_dry", "common", "adult", "Female, {a}y", "Ko'z quriyapti va qizaradi", "Kompyuterda ko'p ishlayman", "Ko'rish pasayganmi?", "ophthalmology", [], ["dry eye", "conjunctivitis"], [], False, "Ophthalmology outpatient", "Screen vision change"),
    _Scenario("rheum_ra", "common", "adult", "Female, {a}y", "Qo'l bo'g'imlari shishgan, ertalab qattiq", "Issiqlik yordam beradi", "Terida qizarish bormi?", "rheumatology", ["internal_medicine"], ["RA", "viral arthritis"], [], False, "Rheumatology workup", "Morning stiffness"),
    _Scenario("rheum_gout", "common", "elderly", "Male, {a}y", "Bosh barmoq birdan shishdi, juda og'riqli", "Isitma {t}, spirt ichganman", "Boshqa bo'g'im?", "rheumatology", ["internal_medicine"], ["gout", "septic joint"], [], True, "Rule out septic joint", "Monoarthritis acute"),
    _Scenario("rheum_lupus", "multi_disease", "adult", "Female, {a}y", "Yuzda kapalak tozma, quyoshdan keyin", "Bo'g'im og'rig'i va charchoq", "Isitma bormi?", "rheumatology", ["internal_medicine", "dermatology"], ["SLE", "Rosacea"], [], False, "Autoimmune workup", "Photosensitive rash"),
    _Scenario("neph_aki", "emergency", "elderly", "Male, {a}y", "Siydik kamaydi, oyoqlar shishgan", "Qusish, nafas qisish", "Dori yoki kontrast olganmisiz?", "internal_medicine", ["emergency_medicine", "urology"], ["AKI", "heart failure"], [], True, "Urgent renal eval", "Oliguria"),
    _Scenario("neph_stone", "common", "adult", "Male, {a}y", "Bel og'rig'i to'lqinli, qusish", "Siydikda qon sezaman", "Isitma bormi?", "urology", ["emergency_medicine"], ["renal colic", "pyelonephritis"], [], False, "Urology if persistent", "Colic pattern"),
    _Scenario("card_af", "common", "elderly", "Female, {a}y", "Yurak aritmiya sezaman, charchoq", "Ba'zan ko'krak og'rig'i", "Antikoagulyant?", "cardiology", ["internal_medicine"], ["AF", "anxiety"], [], False, "Cardiology rhythm", "Irregular pulse"),
    _Scenario("card_hf_el", "common", "elderly", "Male, {a}y", "Nafas qisadi, oyoqlar shishadi", "Tungi yo'tal, vazn ortdi", "Ko'krak og'rig'i?", "cardiology", ["pulmonology"], ["heart failure", "COPD"], [], False, "Cardiology eval", "Volume overload"),
    _Scenario("pul_tb", "infectious", "adult", "Male, {a}y", "Uzoq yo'tal, tungi terlash", "Vazn yo'qotdim, isitma kechqurun", "Kim bilan yashaysiz?", "infectious_diseases", ["pulmonology"], ["TB", "malignancy"], ["weight_loss"], False, "Isolation + workup", "Chronic cough B symptoms"),
    _Scenario("gi_ibd", "multi_disease", "adult", "Male, {a}y", "Qon aralash ich ketish, qorin og'rig'i", "Vazn yo'qotdim, {d} oy", "O'tkazib yuborilgan tashxis bormi?", "gastroenterology", ["internal_medicine"], ["IBD", "infection"], [], False, "GI specialist", "Bloody diarrhea chronic"),
    _Scenario("endo_hyperCa", "rare", "elderly", "Female, {a}y", "Doimiy chanqash, siyish ko'p", "Charchoq va qorin og'rig'i", "Buyrak toshi bormi?", "endocrinology", ["internal_medicine", "emergency_medicine"], ["hypercalcemia", "malignancy"], [], True, "Urgent Ca workup", "Polyuria polydipsia"),
    _Scenario("neuro_ms", "rare", "adult", "Female, {a}y", "Ko'rish birdan xira, keyin yaxshilandi", "Oyoqda uvyish, charchoq", "Issiqlikdan yomonlashadimi?", "neurology", ["ophthalmology"], ["MS", "optic neuritis"], [], False, "Neuro demyelinating", "Relapsing symptoms"),
    _Scenario("neuro_cluster", "common", "adult", "Male, {a}y", "Ko'z atrofida qattiq og'riq, ko'z yoshlanadi", "Har kuni bir vaqtda, {d} hafta", "Burun oqishi bir tomondan?", "neurology", ["ophthalmology"], ["cluster headache", "glaucoma"], [], False, "Neuro headache clinic", "Autonomic features"),
    _Scenario("ortho_oa", "common", "elderly", "Female, {a}y", "Tizza og'rig'i, zinadan chiqqanda", "Ertalab qattiq, keyin yuraman", "Shish va isitma?", "orthopedics", ["rheumatology"], ["osteoarthritis", "RA"], [], False, "Conservative management", "Mechanical pain"),
    _Scenario("ortho_septic", "emergency", "adult", "Male, {a}y", "Tizza birdan shishdi, ishlab bo'lmaydi", "Isitma {t}, diabet bor", "Travma bo'lganmi?", "orthopedics", ["emergency_medicine", "infectious_diseases"], ["septic arthritis", "gout"], [], True, "Emergency joint aspiration", "Hot swollen joint"),
    _Scenario("derm_shingles", "common", "elderly", "Female, {a}y", "Ko'krakning bir tomonida og'riq va tozma", "Tozma chiziq bo'ylab", "Immunitet pasayganmi?", "dermatology", ["neurology"], ["shingles", "contact dermatitis"], [], False, "Antiviral if early", "Dermatomal"),
    _Scenario("derm_sjs", "emergency", "adult", "Male, {a}y", "Yangi dori ichdim, butun tana tozma", "Og'iz yara, isitma {t}", "Ko'rish o'zgarganmi?", "dermatology", ["emergency_medicine"], ["SJS/TEN", "drug rash"], [], True, "Burn unit / ED", "Mucosal involvement"),
    _Scenario("gyne_pcos", "common", "adult", "Female, {a}y", "Hayz tartibsiz, vazn ortyapti", "Tuk o'sishi ko'paygan", "Homiladorlik rejalashtiryapsizmi?", "gynecology", ["endocrinology"], ["PCOS", "thyroid"], [], False, "Gynecology endocrine", "Hyperandrogenism"),
    _Scenario("gyne_endo", "common", "adult", "Female, {a}y", "Hayz juda og'riqli va ko'p", "Qon tampon to'ldirmaydi", "Anemiya belgilari?", "gynecology", ["internal_medicine"], ["endometriosis", "fibroids"], [], False, "Gynecology eval", "Heavy menstrual bleeding"),
    _Scenario("em_overdose", "emergency", "adult", "Female, {a}y", "Ko'p tabletka ichib qo'ydim", "Ko'ngil aynishi, uxlushchanlik", "Qachon ichdingiz?", "emergency_medicine", ["psychiatry"], ["overdose", "suicide attempt"], [], True, "Emergency toxicology", "Time since ingestion"),
    _Scenario("em_heat", "emergency", "adult", "Male, {a}y", "Issiqda ishladim, bosh aylanadi", "Teri quruq, isitma {t}", "Nafas chuqur?", "emergency_medicine", ["internal_medicine"], ["heat stroke", "dehydration"], [], True, "Emergency cooling", "Hot dry skin"),
    _Scenario("mis_food_poison", "misleading", "adult", "Male, {a}y", "Ovqatdan keyin qusish deb o'ylayman", "Qorin o'ng pastda o'tkir og'riq", "Isitma bormi?", "gastroenterology", ["general_surgery", "emergency_medicine"], ["appendicitis", "gastroenteritis"], [], True, "Surgical consult if RLQ", "Food poisoning mislabel"),
    _Scenario("multi_cad_dm", "multi_disease", "elderly", "Male, {a}y, diabetic", "Ko'krak bosimi, nafas qisish", "Oyoq yaralari bor, shakar yuqori", "Og'riq mashqda?", "cardiology", ["endocrinology", "emergency_medicine"], ["ACS", "heart failure"], [], True, "Cardiac workup in DM", "Diabetic + cardiac"),
]


def _scenario_to_case(scenario: _Scenario, global_idx: int, variant: int) -> BlindCase:
    idx = global_idx * 10 + variant
    opener = _v(scenario.user_opener, idx)
    follow = _v(scenario.user_followup, idx)
    probe = _v(scenario.assistant_probe, idx)
    profile = _v(scenario.profile, idx)
    case_id = f"blind_{global_idx + 1:03d}_v{variant + 1}"

    return BlindCase(
        id=case_id,
        category=scenario.category,
        age_group=scenario.age_group,
        patient_profile=profile,
        turns=[
            BlindTurn("user", opener),
            BlindTurn("assistant", probe),
            BlindTurn("user", follow),
        ],
        expected_primary=scenario.expected_primary,
        expected_secondary=list(scenario.expected_secondary),
        expected_differentials=list(scenario.expected_differentials),
        expected_red_flags=list(scenario.expected_red_flags),
        requires_emergency=scenario.requires_emergency,
        expected_recommendation=scenario.expected_recommendation,
        reasoning_rubric=scenario.reasoning_rubric,
    )


def build_blind_cases() -> tuple[BlindCase, ...]:
    all_scenarios = [*_SCENARIOS, *_SCENARIOS_BATCH2]
    cases: list[BlindCase] = []
    for s_idx, scenario in enumerate(all_scenarios):
        for variant in range(10):
            cases.append(_scenario_to_case(scenario, s_idx, variant))
    return tuple(cases[:TARGET_TOTAL])


BLIND_CASES_1000: tuple[BlindCase, ...] = build_blind_cases()
BLIND_CASES_500 = BLIND_CASES_1000  # backwards compatibility
assert len(BLIND_CASES_1000) == TARGET_TOTAL, f"Expected {TARGET_TOTAL}, got {len(BLIND_CASES_1000)}"
