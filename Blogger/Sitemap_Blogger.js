// --- إعدادات السكريبت ---
const config = {
    showImage: true, // اجعلها false إذا أردت إخفاء الصور
    containerId: "sitemapbyMH", // معرف العنصر في القالب
    maxResults: 150, // عدد النتائج في كل دفعة
    defaultImg: "https://4.bp.blogspot.com/-O3EpVMWcoKw/WxY6-6I4--I/AAAAAAAAB2s/KzC0FqUQtkMdw7VzT6oOR_8vbZO6EJc-ACK4BGAYYCw/s72-c/nth.png" // صورة افتراضية
};

// مصفوفة لتخزين أسماء الأقسام
let labels = [];

// 1. تهيئة العنوان الرئيسي
const container = document.getElementById(config.containerId);
if (container) {
    const grotitle = document.createElement("h1");
    grotitle.style.textAlign = "center";
    grotitle.textContent = "فهرس المدونة";
    container.appendChild(grotitle);
}

// 2. دالة جلب الأقسام (Categories) وبناء الهيكل
function GetLabels(e) {
    if (!container) return;
    
    const fragment = document.createDocumentFragment(); // تحسين الأداء: تجميع العناصر
    const categories = e.feed.category;

    for (let i = 0; i < categories.length; i++) {
        labels.push(categories[i].term);

        // إنشاء عنوان القسم
        const titlemh = document.createElement("h2");
        titlemh.className = "h2style";
        titlemh.textContent = categories[i].term;

        // إنشاء القائمة الخاصة بالقسم
        const listul = document.createElement("ul");
        listul.className = `MH${i}`; // تعيين كلاس مميز لكل قائمة

        fragment.appendChild(titlemh);
        fragment.appendChild(listul);
    }
    
    container.appendChild(fragment); // وضع كل شيء في الصفحة مرة واحدة

    // استدعاء دالة جلب المشاركات
    loadScript(`/feeds/posts/default/?start-index=1&max-results=${config.maxResults}&orderby=published&alt=json-in-script&callback=GetSitemap`);
}

// 3. دالة جلب المشاركات (Posts) وتوزيعها
let startIndex = 1;

function GetSitemap(e) {
    if (!e.feed.entry) return; // إنهاء في حال عدم وجود مشاركات

    const entries = e.feed.entry;
    
    // الدوران على كل مشاركة
    for (let i = 0; i < entries.length; i++) {
        const entry = entries[i];
        
        // التأكد من أن المشاركة تابعة لقسم معين
        if (entry.hasOwnProperty("category")) {
            for (let r = 0; r < entry.category.length; r++) {
                const label = entry.category[r].term;
                const labelIndex = labels.indexOf(label);

                // إذا وجدنا القسم في قائمتنا
                if (labelIndex !== -1) {
                    // تحديد رابط المقال
                    let postUrl = "";
                    for (let k = 0; k < entry.link.length; k++) {
                        if (entry.link[k].rel === "alternate") {
                            postUrl = entry.link[k].href;
                            break;
                        }
                    }

                    // إنشاء عنصر المقال
                    const postLi = document.createElement("li");
                    postLi.className = config.showImage ? "item-MH" : "nothing";
                    if (!config.showImage) postLi.style.listStyle = "circle";

                    // تجهيز الصورة
                    let imgTag = "";
                    if (config.showImage) {
                        const imgSrc = entry.media$thumbnail ? entry.media$thumbnail.url : config.defaultImg;
                        imgTag = `<a class="ImageContainer" href="${postUrl}" target="_blank"><img src="${imgSrc}" /></a>`;
                    }

                    // وضع المحتوى داخل الـ li (تم إصلاح خطأ الفاصلة المنقوطة هنا)
                    postLi.innerHTML = `${imgTag}<a class="${config.showImage ? 'Title_url' : 'titleurlnoimg'}" href="${postUrl}" target="_blank">${entry.title.$t}</a>`;

                    // إضافة المقال للقائمة المناسبة
                    const targetUl = document.getElementsByClassName(`MH${labelIndex}`)[0];
                    if (targetUl) targetUl.appendChild(postLi);
                }
            }
        }
    }

    // التحقق مما إذا كان هناك المزيد من المشاركات (Pagination)
    const totalResults = parseInt(e.feed.openSearch$totalResults.$t);
    startIndex += config.maxResults;

    if (totalResults > startIndex) {
        loadScript(`/feeds/posts/default/?start-index=${startIndex}&max-results=${config.maxResults}&orderby=published&alt=json-in-script&callback=GetSitemap`);
    }
}

// دالة مساعدة لتحميل السكريبت ديناميكياً
function loadScript(src) {
    const script = document.createElement("script");
    script.src = src;
    container.appendChild(script);
}

// التشغيل الأولي
loadScript(`/feeds/posts/default/?start-index=1&max-results=${config.maxResults}&orderby=published&alt=json-in-script&callback=GetLabels`);