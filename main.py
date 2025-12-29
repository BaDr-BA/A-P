import requests
import random
import datetime
import pytz
import json
import os
import logging
from hijri_converter import Gregorian

# ============== إعدادات اللوج (Logging) ==============
# قمنا بتبسيط اللوج ليطبع في شاشة GitHub مباشرة
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============== إعدادات المسارات ==============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, 'topic_history.json')
STATS_FILE = os.path.join(BASE_DIR, 'bot_stats.json')
POSTS_FILE = os.path.join(BASE_DIR, 'posts_history.json')

# ============== إعدادات المستخدم (من متغيرات GitHub) ==============
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FB_ACCESS_TOKEN = os.environ.get("FB_ACCESS_TOKEN")
PAGE_ID = os.environ.get("PAGE_ID")

# تحقق بسيط
if not GEMINI_API_KEY or not FB_ACCESS_TOKEN:
    logger.error("⚠️ كارثة: المفاتيح غير موجودة في متغيرات البيئة (Secrets)")

# ============== فئات ودوال الإحصائيات ==============
class BotStatistics:
    def __init__(self):
        self.stats = self.load_stats()

    def load_stats(self):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                'total_posts': 0, 'successful_posts': 0, 'failed_posts': 0,
                'adhkar_posts': 0, 'content_posts': 0, 'questions_posts': 0,
                'last_post_time': None,
                'post_types': {'morning': 0, 'evening': 0, 'long': 0, 'short': 0, 'question': 0}
            }

    def save_stats(self):
        try:
            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"فشل حفظ الإحصائيات: {e}")

    def record_post(self, post_type, success=True):
        self.stats['total_posts'] += 1
        if success:
            self.stats['successful_posts'] += 1
        else:
            self.stats['failed_posts'] += 1

        if post_type in ['morning', 'evening', 'quran_wird']:
            self.stats['adhkar_posts'] += 1
        elif post_type in ['long', 'short']:
            self.stats['content_posts'] += 1
        elif post_type == 'question':
            self.stats['questions_posts'] += 1

        # إذا كان النوع موجود في القائمة نزوده، لو مش موجود ننشئه
        if post_type in self.stats['post_types']:
            self.stats['post_types'][post_type] += 1
        else:
            # إنشاء مفتاح جديد للنوع الجديد تلقائياً
            self.stats['post_types'][post_type] = 1

        self.stats['last_post_time'] = datetime.datetime.now().isoformat()
        self.save_stats()

    def get_stats(self):
        return self.stats

stats = BotStatistics()

# ============== حفظ السجل لمنع التكرار ==============
def load_history():
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'topics': [], 'adhkar_dates': []}
    except json.JSONDecodeError:
        return {'topics': [], 'adhkar_dates': []}

def save_history(history_data):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"فشل حفظ السجل: {e}")

# ============== حفظ تاريخ المنشورات ==============
def load_post_history():
    try:
        with open(POSTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_post_to_history(content_type, content, success=True):
    try:
        history = load_post_history()
        post_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'type': content_type,
            'content_preview': content[:100] + '...' if len(content) > 100 else content,
            'success': success
        }
        history.append(post_entry)
        if len(history) > 100:
            history = history[-100:]

        with open(POSTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"فشل حفظ تاريخ المنشورات: {e}")

# ============== نصوص الأذكار ==============
MORNING_ADHKAR_TEXT = """
1. قراءة آية الكرسي: {الله لا إله إلا هو الحي القيوم لا تأخذه سنة ولا نوم له ما في السماوات وما في الأرض من ذا الذي يشفع عنده إلا بإذنه يعلم ما بين أيديهم وما خلفهم ولا يحيطون بشيء من علمه إلا بما شاء وسع كرسيه السماوات والأرض ولا يؤده حفظهما وهو العلي العظيم} (البقرة:255)، رواه الحاكم وابن حبان.
2. أصبحنا على فطرة الإسلام وكلِمة الإخلاص، ودين نبينا محمد صلى الله عليه وسلم، ومِلَّةِ أبينا إبراهيم، حنيفاً مسلماً، وما كان من المشركين. رواه أحمد.
3. رضيت بالله ربا، وبالإسلام دينا، وبمحمد صلى الله عليه وسلم نبياً. رواه أصحاب السنن.
4. اللهم إني أسألك علماً نافعاً، ورزقاً طيباً، وعملاً متقبلاً. رواه ابن ماجه.
5. اللهم بك أصبحنا، وبك أمسينا، وبك نحيا، وبك نموت، وإليك النشور. رواه أصحاب السنن عدا النسائي.
6. لا إله إلا الله وحده، لا شريك له، له الملك، وله الحمد، وهو على كل شيء قدير. رواه البزار والطبراني في "الدعاء".
7. يا حيُّ يا قيوم برحمتك أستغيثُ، أصلح لي شأني كله، ولا تَكلني إلى نفسي طَرْفَةَ عين أبدًا. رواه البزار.
8. اللهم أنت ربي، لا إله إلا أنت، خلقتني وأنا عبدُك, وأنا على عهدِك ووعدِك ما استطعتُ، أعوذ بك من شر ما صنعتُ، أبوءُ لَكَ بنعمتكَ عَلَيَّ، وأبوء بذنبي، فاغفر لي، فإنه لا يغفرُ الذنوب إلا أنت. رواه البخاري.
9. اللهم فاطر السموات والأرض، عالم الغيب والشهادة، رب كل شيء ومليكه، أشهد أن لا إله إلا أنت, أعوذ بك من شرّ نفسي، ومن شرّ الشيطان وشركه، وأن أقترف على نفسي سوءا، أو أجره إلى مسلم. رواه الترمذي.
10. أصبحنا وأصبح الملك لله، والالحمد لله ولا إله إلا الله وحده لا شريك له، له الملك وله الحمد، وهو على كل شيء قدير، أسألك خير ما في هذا اليوم، وخير ما بعده، وأعوذ بك من شر هذا اليوم، وشر ما بعده، وأعوذ بك من الكسل وسوء الكبر، وأعوذ بك من عذاب النار وعذاب القبر. رواه مسلم.
11. اللهم إني أسألك العفو والعافية في الدنيا والآخرة، اللهم أسألك العفو والعافية في ديني ودنياي وأهلي ومالي، اللهم استر عوراتي، وآمن روعاتي، واحفظني من بين يدي، ومن خلفي، وعن يميني، وعن شمالي، ومن فوقي، وأعوذ بك أن أغتال من تحتي. رواه أبو داود وابن ماجه.
12. بسم الله الذي لا يضر مع اسمه شيء في الأرض ولا في السماء، وهو السميع العليم. (ثلاث مرات). رواه أصحاب السنن عدا النسائي.
13. سبحان الله عدد خلقه، سبحان الله رضا نفسه، سبحان الله زنة عرشه، سبحان الله مداد كلماته. (ثلاث مرات). رواه مسلم.
14. اللهم عافني في بدني، اللهم عافني في سمعي، اللهم عافني في بصري، لا إله إلا أنت، اللهم إني أعوذ بك من الكفر والفقر، اللهم إني أعوذ بك من عذاب القبر، لا إله إلا أنت. (ثلاث مرات). رواه أبو داود.
15. قراءة سور: الإخلاص، والفلق، والناس. ثلاث مرّات. رواه الترمذي.
16. {حسبي الله لا إله إلا هو عليه توكلت وهو رب العرش العظيم}. (سبع مرات). رواه أبو داود.
17. اللهم إني أصبحت، أُشهدك وأُشهد حملة عرشك وملائكتك وجميع خلقك أنك أنت الله، وحدك لا شريك لك وأن محمداً عبدك ورسولك. (أربع مرات). أبو داود والترمذي.
18. لا إله إلا الله وحده، لا شريك له، له الملك، وله الحمد، يحيي ويميت، وهو على كل شيء قدير. (عشر مرات). رواه ابن حبان.
19. سبحان الله وبحمده. أو: سبحان الله العظيم وبحمده. (مائة مرة أو أكثر). رواه مسلم.
20. أستغفر الله. (مائة مرة). رواه ابن أبي شيبة.
21. سبحان الله، والحمد لله، والله أكبر, لا إله إلا الله وحده، لا شريك له، له الملك، وله الحمد، وهوعلى كل شيء قدير. (مائة مرّةٍ أو أكثر). رواه الترمذي.

#اذكار_الصباح #اذكار #ذكر_الله #تهليل #تسبيح"""

EVENING_ADHKAR_TEXT = """
1. قراءة آية الكرسي: {الله لا إله إلا هو الحي القيوم لا تأخذه سنة ولا نوم له ما في السماوات وما في الأرض من ذا الذي يشفع عنده إلا بإذنه يعلم ما بين أيديهم وما خلفهم ولا يحيطون بشيء من علمه إلا بما شاء وسع كرسيه السماوات والأرض ولا يؤده حفظهما وهو العلي العظيم} (البقرة:255). رواه الحاكم وابن حبان.
2. أمسينا على فطرة الإسلام وكلِمة الإخلاص، ودين نبينا محمد صلى الله عليه وسلم، ومِلَّةِ أبينا إبراهيم، حنيفاً مسلماً، وما كان من المشركين. رواه أحمد.
3. رضيت بالله ربا، وبالإسلام دينا، وبمحمد صلى الله عليه وسلم نبياً. رواه أصحاب السنن.
4. اللهم بك أمسينا، وبك أصبحنا، وبك نحيا، وبك نموت، وإليك المصير. رواه أصحاب السنن عدا النسائي.
5. لا إله إلا الله وحده، لا شريك له، له الملك، وله الحمد، وهو على كل شيء قدير. رواه البزار والطبراني في "الدعاء".
6. يا حيُّ يا قيوم برحمتك أستغيثُ، أصلح لي شأني كله، ولا تَكلني إلى نفسي طَرْفَةَ عين أبدًا. رواه البزار.
7. اللهم أنت ربي، لا إله إلا أنت، خلقتني وأنا عبدُك, وأنا على عهدِك ووعدِك ما استطعتُ، أعوذ بك من شر ما صنعتُ، أبوءُ لَكَ بنعمتكَ عَلَيَّ، وأبوء بذنبي، فاغفر لي، فإنه لا يغفرُ الذنوب إلا أنت. رواه البخاري.
8. اللهم فاطر السموات والأرض، عالم الغيب والشهادة، رب كل شيء ومليكه، أشهد أن لا إله إلا أنت, أعوذ بك من شرّ نفسي، ومن شرّ الشيطان وشركه، وأن أقترف على نفسي سوءا، أو أجرُّه إلى مسلم. رواه الترمذي.
9. أمسينا وأمسى الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، اللهم إني أسألك من خير ما في هذه الليلة، وخير ما بعدها، اللهم إني أعوذ بك من شر هذه الليلة وشر ما بعدها، اللهم إني أعوذ بك من الكسل وسوء الكبر، وأعوذ بك من عذاب في النار وعذاب في القبر. رواه مسلم.
10. اللهم إني أسألك العفو والعافية في الدنيا والآخرة، اللهم أسألك العفو والعافية في ديني ودنياي وأهلي ومالي، اللهم استر عوراتي، وآمن روعاتي، واحفظني من بين يدي، ومن خلفي، وعن يميني، وعن شمالي، ومن فوقي، وأعوذ بك أن أغتال من تحتي. رواه أبو داود وابن ماجه.
11. بسم الله الذي لا يضر مع اسمه شيء في الأرض ولا في السماء، وهو السميع العليم. (ثلاث مرات). رواه أصحاب السنن عدا النسائي.
12. أعوذ بكلمات الله التامَّات من شر ما خلق. (ثلاث مرات). رواه مسلم.
13. اللهم عافني في بدني، اللهم عافني في سمعي، اللهم عافني في بصري، لا إله إلا أنت، اللهم إني أعوذ بك من الكفر والفقر، اللهم إني أعوذ بك من عذاب القبر، لا إله إلا أنت. (ثلاث مرات). رواه أبو داود.
14. قراءة سور: الإخلاص، والفلق، والناس. (ثلاث مرّات). رواه الترمذي.
15. قوله تعالى: {حسبي الله لا إله إلا هو عليه توكلت وهو رب العرش العظيم}. (سبع مرات). رواه أبو داود.
16. اللهم إني أمسيت أُشهدك، وأُشهد حملة عرشك، وملائكتك وجميع خلقك، أنك أنت الله، وحدك لا شريك لك، وأن محمداً عبدك ورسولك. (أربع مرات). رواه أبو داود والترمذي.
17. لا إله إلا الله وحده، لا شريك له، له الملك، وله الحمد، يحيي ويميت، وهو على كل شيء قدير. (عشر مرات). رواه ابن حبان.
18. سبحان الله وبحمده. أو: سبحان الله العظيم وبحمده. (مائة مرة أو أكثر). رواه مسلم.
19. أستغفر الله. (مائة مرة). رواه ابن أبي شيبة.
20. سبحان الله، والحمد لله، والله أكبر, لا إله إلا الله وحده، لا شريك له، له الملك، وله الحمد، وهوعلى كل شيء قدير. (مائة مرة أو أكثر). رواه الترمذي.

#اذكار_المساء #اذكار #ذكر_الله #تهليل #تسبيح"""

# ============== الأسئلة التفاعلية ==============
INTERACTIVE_QUESTIONS = [
    "لو قابلت النبي ﷺ اليوم، ما هو السؤال الأول الذي ستسأله؟",
    "ما هو أكبر تحدي إيماني واجهته في حياتك وكيف تغلبت عليه؟",
    "إذا كان لديك فرصة لتغيير عادة واحدة في مجتمعك لتكون أكثر قرباً من الله، ماذا ستكون؟",
    "ما هو الدعاء الذي تشعر أنه أقرب إلى قلبك وتكرره دائماً؟",
    "ما هو الموقف الذي جعلك تبكي من خشية الله في رمضان الماضي؟",
    "إذا طُلب منك كتابة رسالة إلى نفسك قبل 10 سنوات، ما الذي ستخبرها به عن علاقتك بالله؟",
    "ما هو الكتاب (غير القرآن) الذي غير نظرتك للحياة الدينية؟",
    "ما هي الصفة التي تتمنى أن يذكرك الله بها يوم القيامة؟",
    "لو استطعت أن تسافر إلى أي مكان لأداء عبادة، أين ستذهب ولماذا؟",
    "ما هو الشيء الذي تعلمته من الصلاة في أوقات الشدة؟"
]

# ============== الأقسام العشوائية ==============
categories = [
    "دعاء ديني مؤثر وطويل",
    "حكمة إيمانية عميقة ومفصلة",
    "موعظة دينية شاملة",
    "رسالة إيمانية قوية للتفاؤل",
    "نصيحة دينية عملية ومفصلة",
    "قصة قصيرة من السيرة النبوية مع الدروس المستفادة",
    "تحفيز إيماني لتجديد العهد مع الله"
]

# ============== قائمة الموديلات الشاملة (الجيش الكامل) ==============
GEMINI_MODELS = [
    # --- الفئة الأولى: العباقرة (للجودة العالية جداً) ---
    "gemini-3-pro-preview",       # أحدث وأقوى موديل حالياً
    "gemini-2.5-pro",             # وحش الكتابة المستقر
    "gemini-pro-latest",          # آخر إصدار برو مستقر
    "gemini-exp-1206",            # نسخة تجريبية ذكية جداً

    # --- الفئة الثانية: المتوازنة (سرعة وذكاء) ---
    "gemini-2.5-flash",           # الأفضل توازناً حالياً
    "gemini-2.0-flash-exp",       # نسخة فلاش المتطورة
    "gemini-flash-latest",        # آخر تحديث فلاش

    # --- الفئة الثالثة: السريعة والاقتصادية (للاستمرار) ---
    "gemini-2.0-flash",           # الموديل القياسي
    "gemini-2.0-flash-001",       # نسخة مستقرة

    # --- الفئة الرابعة: الاحتياطي الأخير (خفيف جداً) ---
    "gemini-2.5-flash-lite",      # نسخة خفيفة جداً من 2.5
    "gemini-2.0-flash-lite",      # نسخة خفيفة من 2.0
    "gemini-2.0-flash-lite-preview-02-05" # إصدار محدد خفيف
]

# ============== دالة التوليد الذكية (معدلة لمنع العناوين) ==============
def generate_gemini_content_direct(prompt_text, enable_search=False):
    headers = {'Content-Type': 'application/json'}
    tools = [{"google_search": {}}] if enable_search else []

    # هنا التعديل: ضفنا تحذير صريح من العناوين والتسميات
    system_instruction = """
    تعليمات صارمة للنشر:
    1. اكتب النص المطلوب مباشرة للنشر.
    2. ممنوع تماماً كتابة أي مقدمات أو عناوين تصنيفية مثل: (بصيغة سؤال:، دعاء:، رسالة إيمانية:، تذكير:، نوع الموضوع:).
    3. ابدأ بالكلمة الأولى من المحتوى فوراً بدون أي فواصل.
    """

    data = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "tools": tools,
        "systemInstruction": {"parts": [{"text": system_instruction}]}
    }

    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=35)
            if response.status_code == 200:
                result = response.json()
                candidates = result.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if parts:
                        text = parts[0].get('text', "")
                        if text:
                            logger.info(f"✅ نجح التوليد بواسطة: {model}")
                            return text
            elif response.status_code in [429, 500, 503]:
                continue
            else:
                logger.error(f"خطأ من {model}: {response.text}")
                continue
        except Exception as e:
            logger.error(f"فشل الاتصال بـ {model}: {e}")
            continue

    return "Error: All models failed."

# ============== البرومبت الهندسي للنصوص الطويلة ==============
STYLE_PROMPT = """
أنت صانع محتوى ديني واجتماعي موثوق ومؤثر جداً على فيسبوك.
الموضوع المطلوب: [الموضوع]

**⚠️ تعليمات الأمان والدقة (صارمة جداً - الأولوية القصوى):**
1. **تحرَّ الدقة المطلقة في القصص:** ممنوع تحريف قصص الأنبياء أو الصحابة نهائياً. راجع المعلومات مرتين. (مثال للتوضيح: في غار ثور، أبو بكر الصديق هو من خاف، والنبي ﷺ هو من طمأنه بقوله "لا تحزن إن الله معنا").
2. **الاستشهاد:** عند ذكر آية أو حديث، اكتبه بدقة متناهية.
3. **الأسلوب:** لغة بيضاء دافئة (عامية مصرية قريبة من القلب)، مع الحفاظ على هيبة النصوص الدينية.
4. في نهاية المحتوى أكتب كلمات تؤثر على القارئ تحثه على التفاعل (لايك أو قلب أو...) أو التعليق أو المشاركة المناسبين للمحتوى المولد حسب رؤيتك أنت للمحتوى.

**المطلوب:**
حدد "نوع" الموضوع ذهنياً، واكتب عنه بأسلوب "المناسب لك" بناءً على التصنيف التالي:

1️⃣ **إذا كان الموضوع "مشكلة أو ظاهرة سلبية"** (مثل: الضيق، الغلاء، الذنوب):
   - ابدأ بموقف واقعي يلمس الوجع فوراً.
   - قدم "المواساة والحل" برفق ولين، وليس بأسلوب "التوبيخ والترهيب".
   - قدم خطوات عملية بسيطة.

2️⃣ **إذا كان الموضوع "مناسبة دينية أو تريند إيجابي"** (مثل: رمضان، الجمعة):
   - ابدأ بكلمات مبهجة تستشعر عظمة الفرصة.
   - حمس القارئ للعمل الصالح بحب وشوق.

3️⃣ **إذا كان الموضوع "قيمة إيمانية أو روحانية"** (مثل: الرزق، اليقين، الصبر):
   - استخدم أسلوب "التأمل العميق".
   - خاطب القلوب المتعبة والمهمومة لتبث فيها الأمل.

**قواعد التنسيق الصارمة:**
- ابدأ بسؤال أو جملة تخاطب المشاعر فوراً.
- ⛔ لا تستخدم مقدمات نمطية (مثل: مما لا شك فيه، عزيزي القارئ).
- ⛔ لا تضع عنواناً للمنشور (مثل: "نوع الموضوع" أو "المقدمة"). ابدأ بالمتن فوراً.
- اختم بدعاء مؤثر يناسب الموضوع.
"""

# ============== دالة الوقت الحالي بالقاهرة ==============
def get_current_time_cairo():
    try:
        cairo_tz = pytz.timezone('Africa/Cairo')
        return datetime.datetime.now(cairo_tz)
    except Exception as e:
        logger.error(f"خطأ في تحديد الوقت: {e}")
        return datetime.datetime.now(pytz.UTC)

# ============== 📅 دالة المناسبات الإسلامية الشاملة (المطورة) ==============
def get_current_islamic_context():
    """
    تقوم بفحص التاريخ الهجري والميلادي واليوم الأسبوعي
    وتعيد قائمة بكل السياقات المناسبة (جمعة + رمضان + مناسبة خاصة)
    """
    now = get_current_time_cairo()
    today = now.date()
    
    contexts = []

    # 1. فحص يوم الجمعة (والليلة التي تسبقه)
    if now.weekday() == 4: # الجمعة
        contexts.append("يوم الجمعة المبارك")
    elif now.weekday() == 3 and now.hour >= 18: # ليلة الجمعة (الخميس بالليل)
        contexts.append("ليلة الجمعة المباركة")

    # 2. تحويل التاريخ للهجري
    try:
        hijri = Gregorian(today.year, today.month, today.day).to_hijri()
        h_day = hijri.day
        h_month = hijri.month
        
        # --- شهر رمضان (الشهر 9) ---
        if h_month == 9:
            if h_day == 1:
                contexts.append("أول يوم في رمضان واستقبال الشهر الكريم")
            elif h_day >= 20 and h_day % 2 != 0: # الليالي الوترية في العشر الأواخر
                contexts.append("إحدى الليالي الوترية والعشر الأواخر من رمضان")
            elif h_day >= 20:
                contexts.append("العشر الأواخر من رمضان")
            else:
                contexts.append("أيام شهر رمضان المبارك")
        
        # --- ذو الحجة (الشهر 12) ---
        elif h_month == 12:
            if h_day >= 1 and h_day <= 7:
                contexts.append("العشر الأوائل من ذي الحجة")
            elif h_day == 8:
                contexts.append("يوم التروية (الحج)")
            elif h_day == 9:
                contexts.append("يوم عرفة (خير أيام الدنيا)")
            elif h_day == 10:
                contexts.append("يوم عيد الأضحى المبارك")
            elif h_day >= 11 and h_day <= 13:
                contexts.append("أيام التشريق")
        
        # --- محرم (الشهر 1) ---
        elif h_month == 1:
            if h_day == 1:
                contexts.append("رأس السنة الهجرية")
            elif h_day == 9:
                contexts.append("يوم تاسوعاء")
            elif h_day == 10:
                contexts.append("يوم عاشوراء")

        # --- شوال (الشهر 10) ---
        elif h_month == 10:
            if h_day == 1:
                contexts.append("أول أيام عيد الفطر المبارك")
            elif h_day <= 3:
                contexts.append("أيام عيد الفطر")

        # --- ربيع الأول (الشهر 3) ---
        elif h_month == 3 and h_day == 12:
             contexts.append("ذكرى المولد النبوي الشريف")
             
        # --- رجب (الشهر 7) ---
        elif h_month == 7 and h_day == 27:
             contexts.append("ذكرى الإسراء والمعراج")

        # --- شعبان (الشهر 8) ---
        elif h_month == 8 and h_day == 15:
             contexts.append("ليلة النصف من شعبان")

    except Exception as e:
        logger.error(f"خطأ في التاريخ الهجري: {e}")

    return contexts

# ============== دالة جلب موضوع ترندي ==============
def get_trending_topic_with_grounding(base_category):
    history_data = load_history()
    topic_history = history_data.get('topics', [])

    prompt = f"""ابحث عن موضوع ديني أو اجتماعي حالي ومرتبط بـ '{base_category}'.
أعد الرد على الشكل التالي فقط:
[عنوان الموضوع (5 كلمات كحد أقصى)]
[كلمة_مفتاحية_1] [كلمة_مفتاحية_2] [كلمة_مفتاحية_3]

**يجب أن يكون مختلفاً عن:** {', '.join(topic_history[-5:] if topic_history else [])}"""

    response_text = generate_gemini_content_direct(prompt, enable_search=True)

    if "Error" in response_text or not response_text:
        logger.warning("فشل في جلب موضوع ترندي، سيتم استخدام موضوع عشوائي")
        return None, None

    # معالجة الرد بشكل أكثر مرونة
    lines = []
    for line in response_text.split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith('**'):
            lines.append(stripped)

    if len(lines) >= 2:
        topic = lines[0].replace('"', '').replace("'", "").strip()
        if len(lines) > 1:
            keywords_line = lines[1]
            # استخراج الكلمات المفتاحية
            keywords = " ".join([kw.strip() for kw in keywords_line.split() if kw.strip()])
        else:
            keywords = topic.split()[0] if topic else "ديني"

        # التحقق من التكرار
        if topic and topic not in topic_history:
            # تحديث السجل
            topic_history.append(topic)
            if len(topic_history) > 10:
                topic_history.pop(0)

            history_data['topics'] = topic_history
            save_history(history_data)

            return topic, keywords

    return None, None

# ============== 🎨 دالة وصف الصورة لـ Pollinations (النسخة الكاملة) ==============
def generate_image_prompt(text):
    """
    يقرأ النص العربي كاملاً لاستخلاص أدق وصف للمشهد
    """
    # لاحظ هنا: شلنا الـ [:500] وحطينا text زي ما هو
    prompt = f"""
    Role: Elite AI Art Prompt Engineer with advanced Arabic comprehension.

    Task:
    1. Carefully read the FULL Arabic text provided: "{text}" from beginning to end.
    2. Re-read the text multiple times until you fully understand:
    - The complete meaning (explicit and implicit)
    - The emotional tone
    - The spiritual or moral message
    - The final conclusion or lesson
    3. Extract the single most powerful symbolic idea that represents the entire text accurately.

    Your goal:
    Create ONE precise English image prompt that visually represents the FULL meaning of the Arabic text with 100% fidelity, without distortion, omission, or added interpretation.

    ABSOLUTE & NON-NEGOTIABLE RULES:
    - NO text, NO letters, NO numbers, NO calligraphy of any kind inside the image.
    - NO women at all (no female figures, no silhouettes of women, no shadows of women).
    - NO immodesty or prohibited content in any form.
    - The image must be respectful, modest, and spiritually appropriate.
    - The character is not allowed to wear earrings, a necklace, or a hair clip.
    - The presence of a cross in the image is prohibited.

    STYLE REQUIREMENTS:
    - Cinematic lighting
    - Hyper-realistic
    - 8K resolution
    - Deep spiritual and emotional atmosphere
    - Serious, contemplative mood

    OUTPUT CONSTRAINTS:
    - Output ONLY the English image prompt.
    - Maximum length: 70 words.
    - No explanations, no comments, no titles, no extra text.
    """
    
    description = generate_gemini_content_direct(prompt)
    
    # التعامل مع الأخطاء
    if "Error" in description or len(description) < 5: 
        return "Beautiful serene islamic nature landscape, mosque silhouette at sunset, golden hour, cinematic lighting, 8k, highly detailed"
    
    return description

# ============== 🎨 دالة توليد الصورة Pollinations (المعدلة) ==============
def generate_pollinations_image(prompt):
    """
    يقوم بتوليد الصورة وتحميلها محلياً
    """
    try:
        # هنا التعديل: جعلنا الحد 800 حرف بدلاً من 200
        # هذا يسمح بوصف تفصيلي دقيق دون أن يقطع الرابط
        safe_prompt = requests.utils.quote(prompt[:800]) 
        
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1080&height=1080&nologo=true&model=flux"
        # أضفت &model=flux للحصول على جودة أعلى إذا كان متاحاً، أو سيستخدم الافتراضي
        
        response = requests.get(url, timeout=50) # زودنا وقت الانتظار لـ 50 ثانية
        if response.status_code == 200:
            image_path = os.path.join(BASE_DIR, "temp_post_image.jpg")
            with open(image_path, "wb") as f:
                f.write(response.content)
            logger.info("✅ تم تحميل صورة Pollinations بنجاح")
            return image_path
        else:
            logger.error(f"❌ فشل تحميل الصورة، الكود: {response.status_code}")

    except Exception as e:
        logger.error(f"❌ خطأ استثنائي في تحميل الصورة: {e}")
    
    return None

# ============== (المعدل) دالة النشر على فيسبوك ==============
def post_to_facebook(message, image_path=None):
    if not FB_ACCESS_TOKEN or not PAGE_ID:
        logger.error("بيانات الفيسبوك ناقصة")
        return False

    url = f"https://graph.facebook.com/{PAGE_ID}/feed"
    payload = {'message': message, 'access_token': FB_ACCESS_TOKEN}
    files = None

    # إذا كان هناك صورة، نغير الرابط ونجهز الملف
    if image_path:
        url = f"https://graph.facebook.com/{PAGE_ID}/photos"
        try:
            files = {'source': open(image_path, 'rb')}
        except FileNotFoundError:
            logger.error("لم يتم العثور على ملف الصورة")
            return False

    try:
        response = requests.post(url, data=payload, files=files, timeout=60)
        
        # إغلاق الملف إذا تم فتحه
        if files: files['source'].close()
        
        if response.status_code == 200:
            logger.info(f"✅ تم النشر بنجاح! ID: {response.json().get('id')}")
            return True
        else:
            logger.error(f"❌ خطأ فيسبوك: {response.text}")
            return False
    except Exception as e:
        logger.error(f"خطأ استثنائي في النشر: {e}")
        return False
    finally:
        # تنظيف: حذف الصورة فقط إذا كانت مؤقتة (تبدأ بـ temp)
        # أما صور المصحف الأصلية فلا نحذفها
        if image_path and os.path.exists(image_path):
            filename = os.path.basename(image_path)
            if filename.startswith("temp"):
                os.remove(image_path)

# ============== تنظيف النص ==============
def clean_post_text(text):
    # إزالة النجوم الخاصة بـ Markdown (Bolding)
    text = text.replace('**', '').replace('*', '')

    # إزالة الفواصل الزائدة (السطور الفاضية الكتير)
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')

    return text.strip()

# ============== دالة التحقق من وقت الجمعة ==============
def is_friday_mode(now):
    weekday = now.weekday()  # الاثنين=0، الجمعة=4
    hour = now.hour

    # تصحيح: ليلة الجمعة (الخميس بعد العشاء) ويوم الجمعة كامل
    is_thursday_night = (weekday == 3 and hour >= 18)  # الخميس بعد 6 مساءً
    is_friday_full_day = (weekday == 4)  # الجمعة كاملة اليوم

    return is_thursday_night or is_friday_full_day

# ============== دالة التحقق من نشر الأذكار اليوم ==============
def check_adhkar_posted_today(adhkar_type):
    history_data = load_history()
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')

    if 'adhkar_dates' not in history_data:
        history_data['adhkar_dates'] = []

    today_record = f"{today_str}_{adhkar_type}"

    if today_record in history_data['adhkar_dates']:
        return True  # تم النشر اليوم

    # تسجيل النشر اليوم
    history_data['adhkar_dates'].append(today_record)
    # الاحتفاظ بسجل 30 يوم فقط
    if len(history_data['adhkar_dates']) > 30:
        history_data['adhkar_dates'] = history_data['adhkar_dates'][-30:]

    save_history(history_data)
    return False

# ============== دالة دمج المقدمة الذكية مع الأذكار ==============
def get_adhkar_with_dynamic_intro(adhkar_type):
    if adhkar_type == 'morning':
        fixed_text = MORNING_ADHKAR_TEXT
        time_name = "الصباح"
        emoji = "☀️"
    else:
        fixed_text = EVENING_ADHKAR_TEXT
        time_name = "المساء"
        emoji = "🌙"

    # برومبت صارم جداً للمقدمة
    intro_prompt = f"""
    اكتب سطرين فقط كمقدمة دافئة لمنشور أذكار {time_name}.
    تحذير هام: اكتب الكلام مباشرة. ممنوع كتابة كلمات مثل (بصيغة سؤال، دعاء، تذكير).
    مثال للمطلوب: "ما أجمل أن تبدأ يومك بذكر الله، فتشعر بالسكينة تغمر قلبك."
    """

    dynamic_intro = generate_gemini_content_direct(intro_prompt)

    if "Error" in dynamic_intro or len(dynamic_intro) < 5:
        dynamic_intro = f"همسة {time_name}: لا تنسوا تحصين أنفسكم بذكر الله. {emoji}"

    final_post = f"{dynamic_intro}\n\n✨ أذكار {time_name} كاملة:\n{fixed_text}"
    return final_post

# ============== 📖 دالة ورد القرآن (الذكية والشاملة) ==============
def get_next_quran_page_data():
    """
    تجلب الصفحة التالية من مجلد quran_pages الموجود داخل المستودع نفسه
    """
    history = load_history()
    last_page = history.get('last_quran_page', 0)
    current_page = last_page + 1

    # إعادة الختمة إذا وصلنا لآخر صفحة
    if current_page > 604:
        current_page = 1

    # تنسيق الرقم
    possible_filenames = [
        f"{current_page}.jpg",       # الحالة بتاعتك: 1.jpg
        f"{current_page:03}.jpg",    # الحالة القياسية: 001.jpg
        f"{current_page}.png",       # احتياطي png
        f"{current_page:03}.png"     # احتياطي png مرقم
    ]
    
    found_path = None

    for filename in possible_filenames:
        check_path = os.path.join(BASE_DIR, 'quran_pages', filename)
        if os.path.exists(check_path):
            found_path = check_path
            break
    
    if found_path:
        logger.info(f"✅ تم العثور على صفحة المصحف: {found_path}")
        return current_page, found_path
    else:
        logger.error(f"❌ خطأ: لم يتم العثور على صورة الصفحة رقم {current_page} داخل مجلد quran_pages")
        # طباعة المسارات التي حاول البحث فيها للمساعدة في التشخيص
        logger.info(f"حاولت البحث عن: {possible_filenames}")
        return None, None

# ============== 🏷️ دالة تحديد اسم السورة (للهاشتاج) ==============
def get_surah_hashtag(page_number):
    """
    تحدد اسم السورة (أو السور) بناءً على رقم الصفحة
    """
    # الخريطة الآن تربط رقم الصفحة بـ "قائمة" سور
    surah_map = {
        1: ["الفاتحة"], 2: ["البقرة"], 50: ["آل_عمران"], 77: ["النساء"],
        106: ["المائدة"], 128: ["الأنعام"], 151: ["الأعراف"], 177: ["الأنفال"],
        187: ["التوبة"], 208: ["يونس"], 221: ["هود"], 235: ["يوسف"],
        249: ["الرعد"], 255: ["إبراهيم"], 262: ["الحجر"], 267: ["النحل"],
        282: ["الإسراء"], 293: ["الكهف"], 305: ["مريم"], 312: ["طه"],
        322: ["الأنبياء"], 332: ["الحج"], 342: ["المؤمنون"], 350: ["النور"],
        359: ["الفرقان"], 367: ["الشعراء"], 377: ["النمل"], 385: ["القصص"],
        396: ["العنكبوت"], 404: ["الروم"], 411: ["لقمان"], 415: ["السجدة"],
        418: ["الأحزاب"], 428: ["سبأ"], 434: ["فاطر"], 440: ["يس"],
        446: ["الصافات"], 453: ["ص"], 458: ["الزمر"], 467: ["غافر"],
        477: ["فصلت"], 483: ["الشورى"], 489: ["الزخرف"], 496: ["الدخان"],
        499: ["الجاثية"], 502: ["الأحقاف"], 507: ["محمد"], 511: ["الفتح"],
        515: ["الحجرات"], 518: ["ق"], 520: ["الذاريات"], 523: ["الطور"],
        526: ["النجم"], 528: ["القمر"], 531: ["الرحمن"], 534: ["الواقعة"],
        537: ["الحديد"], 542: ["المجادلة"], 545: ["الحشر"], 549: ["الممتحنة"],
        551: ["الصف"], 553: ["الجمعة"], 554: ["المنافقون"], 556: ["التغابن"],
        558: ["الطلاق"], 560: ["التحريم"], 562: ["الملك"], 564: ["القلم"],
        566: ["الحاقة"], 568: ["المعارج"], 570: ["نوح"], 572: ["الجن"],
        574: ["المزمل"], 575: ["المدثر"], 577: ["القيامة"], 578: ["الإنسان"],
        580: ["المرسلات"], 582: ["النبأ"], 583: ["النازعات"], 585: ["عبس"],
        586: ["التكوير"], 587: ["الانفطار", "المطففين"], 589: ["الانشقاق"],
        590: ["البروج"], 591: ["الطارق", "الأعلى"], 592: ["الغاشية"],
        593: ["الفجر"], 594: ["البلد"], 595: ["الشمس", "الليل"],
        596: ["الضحى", "الشرح"], 597: ["التين", "العلق"],
        598: ["القدر", "البينة"], 599: ["الزلزلة", "العاديات"],
        600: ["القارعة", "التكاثر"], 
        601: ["العصر", "الهمزة", "الفيل"],
        602: ["قريش", "الماعون", "الكوثر"],
        603: ["الكافرون", "النصر", "المسد"],
        604: ["الإخلاص", "الفلق", "الناس"]
    }

    # البحث عن السورة المناسبة للصفحة الحالية
    # نقوم بترتيب الصفحات تصاعدياً ونأخذ آخر سورة بدأت قبل أو في هذه الصفحة
    current_surahs = ["القرآن_الكريم"]
    
    # ترتيب المفاتيح لضمان البحث الصحيح
    sorted_pages = sorted(surah_map.keys())
    
    for start_page in sorted_pages:
        if page_number >= start_page:
            current_surahs = surah_map[start_page]
        else:
            break
            
    # تجميع الهاشتاجات بمسافات
    # النتيجة ستكون مثل: #سورة_النبأ أو #سورة_الإخلاص #سورة_الفلق #سورة_الناس
    hashtags = " ".join([f"#سورة_{name}" for name in current_surahs])
    return hashtags

# ============== ✍️ دالة توليد نص الورد ==============
def generate_wird_text(page_number):
    """
    توليد نص تشجيعي لقراءة الورد اليومي
    """
    prompt = f"""
    اكتب منشوراً قصيراً جداً (سطر أو سطرين) للفيسبوك.
    المحتوى: تذكير لطيف وحماسي لمتابعي الصفحة بقراءة ورد القرآن اليومي (الصفحة رقم {page_number}).
    الأسلوب: روحاني، محفز، دافيء، وبدون أي مقدمات مثل "إليك المنشور".
    خاتمة: دعاء قصير بقبول العمل.
    """
    return generate_gemini_content_direct(prompt)

# ============== 🔄 دالة تحديث سجل القرآن ==============
def update_quran_history(page_number):
    """
    تحديث سجل آخر صفحة تم نشرها لضمان التسلسل
    """
    history = load_history()
    history['last_quran_page'] = page_number
    # تسجيل أننا نشرنا الورد اليوم لمنع التكرار
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    if 'adhkar_dates' not in history:
        history['adhkar_dates'] = []
    
    # نضيف العلامة المميزة للورد
    history['adhkar_dates'].append(f"{today_str}_quran_wird")
    
    # نحتفظ بآخر 30 سجل فقط لعدم تضخم الملف
    if len(history['adhkar_dates']) > 30:
        history['adhkar_dates'] = history['adhkar_dates'][-30:]
        
    save_history(history)

# ============== الدالة الرئيسية لتشغيل البوت ==============
def run_bot():
    try:
        now = get_current_time_cairo()
        current_hour = now.hour
        current_minute = now.minute

        logger.info(f"🚀 بدء تشغيل البوت - الساعة: {current_hour}")

        post_content = ""
        image_path = None
        content_type = "unknown"
        
        # 1. الأذكار (الصباح 5-7)
        if 5 <= current_hour <= 7:
            if not check_adhkar_posted_today('morning'):
                post_content = get_adhkar_with_dynamic_intro('morning')
                content_type = "morning"

        # 2. 📖 ورد القرآن (العصرية: الساعة 13 إلى 15 أي 1 ظهراً لـ 3:59 عصراً)
        elif 13 <= current_hour <= 15: 
            # نتحقق هل تم نشر الورد اليوم أم لا
            if not check_adhkar_posted_today('quran_wird'):
                logger.info("بدء تجهيز ورد القرآن اليومي...")
                page_num, quran_img_path = get_next_quran_page_data()
                
                if page_num and quran_img_path:
                    # توليد النص
                    text_intro = generate_wird_text(page_num)
                    
                    # 🔥 هنا الإضافة: جلب اسم السورة كهاشتاج
                    surah_hashtag = get_surah_hashtag(page_num)
                    
                    if "Error" not in text_intro:
                        post_content = f"📖 وردك اليومي من القرآن الكريم\nالصفحة رقم: {page_num}\n\n{text_intro}\n\n{surah_hashtag} #القرآن_الكريم #ورد_يومي #تدبر"
                        image_path = quran_img_path
                        content_type = "quran_wird"
                        
                        # ملاحظة: سيتم تحديث رقم الصفحة في السجل فقط إذا نجح النشر في الأسفل
        
        # 3. الأذكار (المساء 16-18)
        elif 16 <= current_hour <= 18:
            if not check_adhkar_posted_today('evening'):
                post_content = get_adhkar_with_dynamic_intro('evening')
                content_type = "evening"
            
        # 4. محتوى ذكي (يدمج المناسبات)
        if not post_content:
            # جلب كل السياقات الحالية
            current_contexts = get_current_islamic_context()
            combined_occasion = None
            
            # دمج السياقات في جملة واحدة
            if current_contexts:
                # لو فيه جمعة ورمضان هتكون: "يوم الجمعة المبارك بالتزامن مع العشر الأواخر من رمضان"
                combined_occasion = " بالتزامن مع ".join(current_contexts)
                base_category = f"فضل {combined_occasion} وأفضل الأعمال والعبادات المستحبة فيها"
                
                # إعطاء أولوية قصوى للمنشور الطويل في المناسبات المزدوجة
                if len(current_contexts) > 1:
                    force_long_post = True  # مناسبة قوية = منشور طويل
                else:
                    force_long_post = False
            else:
                combined_occasion = None
                base_category = None
                force_long_post = False

            # تحديد نوع المنشور (طويل/قصير)
            # لو في مناسبة قوية (جمعة + رمضان) نخليه طويل بنسبة أكبر
            is_long_post = force_long_post or (random.random() <= 0.25)

            if is_long_post:
                # --- مسار المحتوى الطويل ---
                if not base_category:
                     # القائمة الطويلة الاحتياطية (لو مفيش مناسبة خاصة)
                    trending_triggers = [
                        "أكثر المشاكل النفسية أو الاجتماعية التي يشتكي منها الناس في مصر هذا الأسبوع وعلاجها في القرآن والسنة",
                        "ظاهرة سلبية أو سلوك خاطئ انتشر مؤخراً على السوشيال ميديا وعلاجه بأسلوب نصيحة محبة ومشفق",
                        "تريند إيجابي أو قصة إنسانية مؤثرة عن جبر الخواطر أو الرزق حدثت مؤخراً وشرح الدروس المستفادة منها",
                        "قصة واقعية حديثة تحمل عبرة قوية عن عوض الله والرضا بالقضاء وتناسب أحوال الناس",
                        "سنة مهجورة أو عبادة يغفل عنها الناس تناسب الأجواء الحالية (حر/برد/امتحانات/أعياد/ضيق معيشة)",
                        "معلومة فقهية أو عقدية بسيطة يجهلها الكثيرون وتصحح مفاهيم خاطئة منتشرة حالياً",
                        "تفسير مؤثر لآية قرآنية تواسي الناس في ضغوط الحياة الحالية وتطمئن قلوبهم وتزيد اليقين",
                        "موقف أو قصة من السيرة النبوية فيها مواساة وحل لما يمر به الناس اليوم من ضيق أو قلق",
                        "موعظة دينية قوية تمس الواقع وتتحدث عن حسن الظن بالله واليقين في ظل الظروف الحالية",
                        "دعاء شامل ومؤثر يلامس حاجات الناس المادية والنفسية في هذا الوقت تحديدا"
                    ]
                    base_category = random.choice(trending_triggers)
                
                # ... تكملة كود جلب الموضوع والتوليد كما هو ...
                topic, keywords = get_trending_topic_with_grounding(base_category)
                if not topic: 
                    topic = base_category
                    keywords = topic.split()[0] if topic else "ديني"                

                selected_topic = topic

                # إنشاء المحتوى الطويل
                prompt = STYLE_PROMPT.replace('[الموضوع]', topic)
                
                # طلب 5 هاشتاجات شائعة
                hashtag_prompt = f"اكتب بالضبط 5 هاشتاجات دينية قصيرة ومشهورة لفيسبوك عن: {topic}. افصل بينهم بمسافة فقط (سطر واحد). ممنوع القوائم أو الترقيم. مثال: #الله #دعاء #إسلام"
                hashtags_response = generate_gemini_content_direct(hashtag_prompt)

                post_content = generate_gemini_content_direct(prompt)

                # إضافة الهاشتاجات إذا كانت موجودة
                if hashtags_response and "Error" not in hashtags_response:
                    post_content += f"\n\n{hashtags_response}"

                # صورة (إجباري للطويل)
                img_prompt = generate_image_prompt(post_content)
                image_path = generate_pollinations_image(img_prompt)
                content_type = "long"
                
            else:
                # ==================== مسار المنشورات الخفيفة (75%) ====================
                
                # إرجاع منطق الـ 30% للسؤال و 70% للقصير
                if random.random() < 0.3:
                    # ==================== أ. مسار السؤال التفاعلي ====================
                    content_type = "question"
                    
                    if combined_occasion:
                        # (الجديد) سؤال ذكي موجه للمناسبة الحالية
                        part1 = f"اكتب سؤالاً دينياً تفاعلياً واحداً للنقاش على فيسبوك يدور حول {combined_occasion}. السؤال يجب أن يكون عميقاً ومحفزاً للتعليقات. بدون مقدمات."
                    else:
                        # (القديم) السؤال العام
                        part1 = "اكتب سؤالا دينيا تفاعليا واحدا فقط للمتابعين على فيسبوك لزيادة التعليقات. السؤال يجب أن يكون عميقا ومؤثرا أو بسيطا. بدون مقدمات."
                    
                    post_content = generate_gemini_content_direct(part1)

                    # توليد صورة علامة استفهام مميزة للسؤال
                    question_img_prompt = "A giant, 3D, golden question mark in the center, mysterious dark background, cinematic lighting, 8k resolution, highly detailed, no text, spiritual atmosphere"
                    image_path = generate_pollinations_image(question_img_prompt)

                else:
                    # ==================== ب. مسار المحتوى القصير ====================
                    content_type = "short"
                    
                    if combined_occasion:
                        # قائمة الـ 16 نوع موجهة للمناسبة
                        simple_prompts = [
                            f"اكتب حكمة دينية أو إيمانية واحدة عن {combined_occasion}.",
                            f"اكتب موعظة دينية أو إيمانية قصيرة ومباشرة تناسب {combined_occasion}.",
                            f"اكتب رسالة دينية أو إيمانية قصيرة عن {combined_occasion}.",
                            f"اكتب دعاء ديني أو إيماني مؤثر قصير عن {combined_occasion}.",
                            f"اكتب موقف أو قصة قصيرة من السيرة النبوية مع الدروس المستفادة عن {combined_occasion}.",
                            f"اكتب موقف أو قصة قصيرة من الصحابة مع الدروس المستفادة عن {combined_occasion}.",
                            f"اكتب موقف أو قصة قصيرة دينية أو إيمانية بعيدًا عن الرسول والصحابة مع الدروس المستفادة عن {combined_occasion}.",
                            f"اكتب تحفيز ديني أو إيماني قصير عن {combined_occasion}.",
                            f"اكتب معلومة دينية أو إيمانية قصيرة عن {combined_occasion}.",
                            f"اكتب عبارة دينية أو إيمانية قصيرة عن {combined_occasion}.",
                            f"اكتب إلهام ديني أو إيماني قصيرة عن {combined_occasion}.",
                            f"اكتب قاعدة دينية أو إيمانية مختصرة قصيرة عن {combined_occasion}.",
                            f"اكتب تنبيهًا دينيًا أو إيمانيًا قصيرًا عن {combined_occasion}.",
                            f"اكتب ذكرًا ديني أو إيماني قصير عن {combined_occasion}.",
                            f"اكتب مبدأ ديني أو إيماني قصير عن {combined_occasion}.",
                            f"اكتب نصيحة دينية أو إيمانية عملية قصيرة عن {combined_occasion}.",
                            f"اكتب تذكير بسنة مهجورة أو عمل صالح مستحب في {combined_occasion}.",
                            f"اكتب رسالة تفاؤل وبشرى قصيرة مرتبطة بـ {combined_occasion}."
                        ]
                    else:
                        # القائمة العادية (القديمة)
                        simple_prompts = [
                            "اكتب حكمة دينية أو إيمانية واحدة.",
                            "اكتب موعظة دينية أو إيمانية قصيرة ومباشرة.",
                            "اكتب رسالة دينية أو إيمانية قصيرة.",
                            "اكتب دعاء ديني أو إيماني مؤثر قصير.",
                            "اكتب موقف أو قصة قصيرة من السيرة النبوية مع الدروس المستفادة.",
                            "اكتب موقف أو قصة قصيرة من الصحابة مع الدروس المستفادة.",
                            "اكتب موقف أو قصة قصيرة دينية أو إيمانية بعيدًا عن الرسول والصحابة مع الدروس المستفادة.",
                            "اكتب تحفيز ديني أو إيماني قصير.",
                            "اكتب معلومة دينية أو إيمانية قصيرة.",
                            "اكتب عبارة دينية أو إيمانية قصيرة.",
                            "اكتب إلهام ديني أو إيماني قصيرة.",
                            "اكتب قاعدة دينية أو إيمانية مختصرة قصيرة.",
                            "اكتب تنبيهًا دينيًا أو إيمانيًا قصيرًا.",
                            "اكتب ذكرًا ديني أو إيماني قصير.",
                            "اكتب مبدأ ديني أو إيماني قصير.",
                            "اكتب تذكير بسنة مهجورة أو عمل صالح مستحب.",
                            "اكتب نصيحة دينية أو إيمانية عملية قصيرة."
                        ]
                    
                    post_content = generate_gemini_content_direct(random.choice(simple_prompts))

        # النشر على فيسبوك
        if post_content and len(post_content) > 10 and "Error" not in post_content:
            cleaned_content = clean_post_text(post_content)

            # النشر
            success = post_to_facebook(cleaned_content, image_path)
            
            if success:
                # إذا كان النوع ورد قرآن، نقوم بتحديث رقم الصفحة في السجل الآن
                if content_type == "quran_wird":
                    # نستخرج رقم الصفحة من النص أو نعيد جلبه (الأفضل تمريره، لكن للتبسيط سنعيد منطق الحساب)
                    # هنا سنقوم باستدعاء دالة التحديث التي أنشأناها بالأعلى
                    # ملاحظة: نحن بحاجة لمعرفة رقم الصفحة الذي تم نشره لتخزينه
                    # سنجلبه من history القديم + 1
                    hist = load_history()
                    last = hist.get('last_quran_page', 0)
                    update_quran_history(last + 1)

            # تسجيل الإحصائيات
            stats.record_post(content_type, success)

            # حفظ في السجل
            save_post_to_history(content_type, cleaned_content, success)
        else:
            logger.info("لم يتم النشر (إما تم نشر سابقاً أو الوقت غير مناسب أو خطأ في التوليد)")

    except Exception as e:
        logger.error(f"خطأ غير متوقع في تشغيل البوت: {e}")

if __name__ == '__main__':
    # 1. تهيئة ملف الإحصائيات (قاموس)
    if not os.path.exists(STATS_FILE):
        default_stats = {
            'total_posts': 0, 'successful_posts': 0, 'failed_posts': 0,
            'adhkar_posts': 0, 'content_posts': 0, 'questions_posts': 0,
            'last_post_time': None,
            'post_types': {'morning': 0, 'evening': 0, 'long': 0, 'short': 0, 'question': 0}
        }
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_stats, f, ensure_ascii=False, indent=4)

    # 2. تهيئة ملف السجل (قاموس)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump({'topics': [], 'adhkar_dates': []}, f, ensure_ascii=False, indent=4)

    # 3. تهيئة ملف أرشيف المنشورات (قائمة)
    if not os.path.exists(POSTS_FILE):
        with open(POSTS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=4)

    run_bot()









