# PS4 Tools Mobile

واجهة iOS عربية لإدارة مشروع تحويل المودات عبر GitHub Actions، مصممة للاستخدام من iPhone وiPad دون الحاجة إلى كمبيوتر محلي.

## بناء IPA ونشرها تلقائيًا

كل دفعة تغيّر ملفات `ios/**` على فرع `feature/ps4tools-ios-app` تشغّل Workflow باسم **Build IPA and Publish GitHub Release**. عند نجاح البناء، ينشئ GitHub Release جديدًا ويرفق به:
- `PS4ToolsMobile.ipa`
- سجل البناء `ios-iphoneos-build.log`

يمكن تشغيل البناء يدويًا من تبويب Actions باستخدام `workflow_dispatch`.

**مهم:** ملف IPA الناتج غير موقّع لأن المستودع لا يحتوي على شهادة توزيع أو ملفات توقيع. يمكن استخدامه كملف مصدر لأداة توقيع iOS مثل SideStore، لكنه ليس مثبتًا مباشرة قبل التوقيع. نجاح Workflow يثبت نجاح البناء والتغليف فقط، ولا يثبت اختبار التطبيق على جهاز فعلي.

## ما الذي يفعله التطبيق؟

1. يتحقق من GitHub Personal Access Token ويحفظه في iOS Keychain.
2. ينشئ مستودع عمل مستقل (بحسب إعداد القالب وصلاحيات GitHub).
3. يستورد ملفات المود من تطبيق Files ويرفعها إلى مجلد `input/`.
4. يرسل طلب تشغيل إلى Workflow التحويل.
5. يعرض للمستخدم حالة الطلب وروابط النتائج.

## بناء محلي عبر Xcode

المشروع مولّد بواسطة XcodeGen:

```sh
cd ios
xcodegen generate
xcodebuild -project PS4ToolsMobile.xcodeproj -scheme PS4ToolsMobile -sdk iphonesimulator -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build
```

## صلاحيات GitHub المطلوبة داخل التطبيق

استخدم Fine-grained Personal Access Token مع الصلاحيات اللازمة للمستودعات التي سيعمل عليها التطبيق:
- Contents: Read and write
- Actions: Read and write
- Administration: Read and write فقط إذا كان التطبيق سيُنشئ مستودعات من قالب أو يعدّل إعداداته.

لا تضع الرمز داخل ملفات المشروع. التطبيق يحفظه محليًا في Keychain.

## حدود الرفع

يرفع التطبيق الملفات عبر GitHub Contents API، وحد الملف الواحد 100 MB. الملفات الأكبر تحتاج مسار رفع بديلًا.

## حالة التنفيذ

Workflow إصدار IPA أُضيف إلى هذا الفرع. يلزم انتظار تشغيل GitHub Actions والتحقق من نجاحه وظهور ملف IPA في صفحة Releases قبل اعتبار النسخة مبنية.
