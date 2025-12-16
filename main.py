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

        if post_type in ['morning', 'evening']:
            self.stats['adhkar_posts'] += 1
        elif post_type in ['long', 'short']:
            self.stats['content_posts'] += 1
        elif post_type == 'question':
            self.stats['questions_posts'] += 1

        if post_type in self.stats['post_types']:
            self.stats['post_types'][post_type] += 1

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
3. **الأسلوب:** لغة بيضاء دافئة (فصحى مبسطة قريبة من القلب)، مع الحفاظ على هيبة النصوص الدينية.

**المطلوب:**
حدد "نوع" الموضوع ذهنياً، واكتب عنه بأسلوب "الصديق الناصح" بناءً على التصنيف التالي:

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

# ============== دالة التحقق من المناسبات الإسلامية ==============
def check_islamic_occasion():
    now = get_current_time_cairo()
    today = now.date()

    # التحقق من يوم الجمعة
    if today.weekday() == 4:
        return "يوم الجمعة المبارك"

    # التحقق من التاريخ الهجري
    try:
        hijri_date = Gregorian(today.year, today.month, today.day).to_hijri()

        major_occasions = {
            '01/01': "بداية العام الهجري الجديد",
            '10/01': "يوم عاشوراء",
            '12/03': "المولد النبوي الشريف",
            '27/07': "الإسراء والمعراج",
            '15/08': "ليلة النصف من شعبان",
            '01/09': "بداية شهر رمضان المبارك",
            '01/10': "أول أيام عيد الفطر المبارك",
            '09/12': "يوم عرفة",
            '10/12': "يوم عيد الأضحى المبارك",
        }

        current_hijri_key = f"{hijri_date.day:02d}/{hijri_date.month:02d}"

        if current_hijri_key in major_occasions:
            return major_occasions[current_hijri_key]

        # شهر رمضان كامل
        if hijri_date.month == 9 and hijri_date.day > 1 and hijri_date.day < 27:
            return "أيام شهر رمضان المبارك"

    except Exception as e:
        logger.error(f"خطأ في تحويل التاريخ الهجري: {e}")

    return None

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

# ============== 🎨 (الجديد) دالة وصف الصورة لـ Pollinations ==============
def generate_image_prompt(text):
    """
    يحلل النص ويطلب من Gemini وصفاً بالإنجليزية للصورة
    """
    prompt = f"""
    Read this Arabic text: "{text[:400]}..."
    Task: Write a detailed vivid description in English for a background image suitable for this text.
    STRICT RULES:
    1. NO humans, NO faces, NO text in the image.
    2. Focus on: Nature, Light, Mosques, Sky, Abstract Islamic art.
    3. Output ONLY the English description.
    """
    description = generate_gemini_content_direct(prompt)
    if "Error" in description: return "Beautiful serene islamic nature landscape mosque at sunset cinematic lighting"
    return description

# ============== 🎨 (الجديد) دالة توليد الصورة Pollinations ==============
def generate_pollinations_image(prompt):
    """
    يقوم بتوليد الصورة وتحميلها محلياً
    """
    try:
        # تنظيف البرومبت للرابط
        safe_prompt = requests.utils.quote(prompt[:200]) # نأخذ أول 200 حرف فقط لتجنب الأخطاء
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1080&height=1080&nologo=true"
        
        response = requests.get(url, timeout=40)
        if response.status_code == 200:
            image_path = os.path.join(BASE_DIR, "temp_post_image.jpg")
            with open(image_path, "wb") as f:
                f.write(response.content)
            logger.info("✅ تم تحميل صورة Pollinations بنجاح")
            return image_path
    except Exception as e:
        logger.error(f"❌ فشل تحميل الصورة: {e}")
    
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
        # تنظيف: حذف الصورة بعد النشر
        if image_path and os.path.exists(image_path):
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
        
        # 2. الأذكار (المساء 16-18)
        elif 16 <= current_hour <= 18:
            if not check_adhkar_posted_today('evening'):
                post_content = get_adhkar_with_dynamic_intro('evening')
                content_type = "evening"
            
        # 3. محتوى عشوائي (إذا لم يكن وقت أذكار)
        if not post_content:
            occasion = check_islamic_occasion()
            
            in_friday_mode = False
            if now.weekday() == 4 or (now.weekday() == 3 and now.hour >= 18):
                in_friday_mode = True

            # 25% طويل، 75% قصير/سؤال (نفس نسب القديم)
            if random.random() <= 0.25:
                # --- مسار المحتوى الطويل ---
                if in_friday_mode:
                    base_category = "فضل يوم الجمعة وفضائل الصلاة على النبي وقراءة سورة الكهف"
                elif occasion:
                    base_category = f"فضل {occasion} وأحب الأعمال المستحبة فيه"
                else:
                    # [cite_start]القائمة الطويلة الكاملة (من القديم) [cite: 169-173]
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
                
                # جلب موضوع ترندي
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
                # --- مسار المحتوى القصير/الأسئلة ---
                if random.random() < 0.3:
                    # توليد السؤال من Gemini
                    part1 = "اكتب سؤالا دينيا تفاعليا واحدا فقط للمتابعين على فيسبوك لزيادة التعليقات. السؤال يجب أن يكون عميقا ومؤثرا. بدون مقدمات."
                    post_content = generate_gemini_content_direct(part1)
                    content_type = "question"
                else:
                    # محتوى قصير
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
                        "اكتب نصيحة دينية أو إيمانية عملية قصيرة."
                    ]

                    # قائمة الجمعة
                    if in_friday_mode:
                        simple_prompts = [
                            "اكتب حكمة دينية أو إيمانية عن يوم الجمعة.",
                        "اكتب موعظة دينية أو إيمانية قصيرة ومباشرة عن يوم الجمعة.",
                        "اكتب رسالة دينية أو إيمانية قصيرة موجهة ليوم الجمعة.",
                        "اكتب دعاء ديني أو إيماني مؤثر قصير ليوم الجمعة.",
                        "اكتب موقفًا أو قصة قصيرة من السيرة النبوية تتعلق بيوم الجمعة مع الدروس المستفادة.",
                        "اكتب موقفًا أو قصة قصيرة من الصحابة تتعلق بيوم الجمعة مع الدروس المستفادة.",
                        "اكتب موقف أو قصة قصيرة دينية أو إيمانية بعيدًا عن الرسول والصحابة مرتبطة بيوم الجمعة مع الدروس المستفادة.",
                        "اكتب تحفيزًا دينيًا أو إيمانيًا قصيرًا خاصًا بيوم الجمعة.",
                        "اكتب معلومة دينية أو إيمانية قصيرة عن يوم الجمعة.",
                        "اكتب عبارة دينية أو إيمانية قصيرة عن يوم الجمعة.",
                        "اكتب إلهامًا دينيًا أو إيمانيًا قصيرًا ليوم الجمعة.",
                        "اكتب قاعدة دينية أو إيمانية مختصرة قصيرة عن يوم الجمعة.",
                        "اكتب تنبيهًا دينيًا أو إيمانيًا قصيرًا متعلقًا بيوم الجمعة.",
                        "اكتب ذكرًا دينيًا أو إيمانيًا قصيرًا يُقال في يوم الجمعة.",
                        "اكتب مبدأ دينيًا أو إيمانيًا قصيرًا مرتبطًا بيوم الجمعة.",
                        "اكتب نصيحة دينية أو إيمانية عملية قصيرة خاصة بيوم الجمعة."
                    ]

                    post_content = generate_gemini_content_direct(random.choice(simple_prompts))
                    content_type = "short"
                
                # صورة (50% احتمال للقصير)
                if random.random() < 0.5:
                    img_prompt = generate_image_prompt(post_content)
                    image_path = generate_pollinations_image(img_prompt)

        # النشر على فيسبوك
        if post_content and len(post_content) > 10 and "Error" not in post_content:
            cleaned_content = clean_post_text(post_content)

            # النشر
            success = post_to_facebook(cleaned_content, image_path)

            # تسجيل الإحصائيات
            stats.record_post(content_type, success)

            # حفظ في السجل
            save_post_to_history(content_type, cleaned_content, success)
        else:
            logger.info("لم يتم النشر (إما تم نشر الأذكار سابقاً أو خطأ في التوليد)")

    except Exception as e:
        logger.error(f"خطأ غير متوقع في تشغيل البوت: {e}")

if __name__ == '__main__':
    # تهيئة الملفات
    for file in [HISTORY_FILE, STATS_FILE, POSTS_FILE]:
        if not os.path.exists(file):
            with open(file, 'w', encoding='utf-8') as f: json.dump([], f)
    run_bot()