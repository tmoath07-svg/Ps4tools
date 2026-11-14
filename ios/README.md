# PS4 Tools Mobile

واجهة iOS عربية لإدارة مشروع تحويل المودات عبر GitHub Actions، مصممة للاستخدام من iPhone وiPad دون الحاجة إلى كمبيوتر محلي.

## ما الذي يفعله التطبيق؟

1. يتحقق من GitHub Personal Access Token ويحفظه في iOS Keychain.
2. يحوّل مستودع `tmoath07-svg/Ps4tools` إلى GitHub Template عند أول استخدام.
3. ينشئ مستودع عمل مستقل من القالب، متضمنًا Workflow وأدوات التحويل وملف Toolkit ZIP.
4. يستورد ملفات المود من تطبيق Files ويرفعها إلى مجلد `input/`.
5. يرسل طلب تشغيل إلى Workflow `zokii-studio-dlc-fixed.yml`.
6. يعرض للمستخدم حالة الطلب، ويمكن تنزيل النتائج من Actions Artifacts.

## بناء التطبيق

المشروع مولّد بواسطة XcodeGen:

```sh
cd ios
xcodegen generate
xcodebuild -project PS4ToolsMobile.xcodeproj -scheme PS4ToolsMobile -sdk iphonesimulator -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build
```

## صلاحيات GitHub المطلوبة

استخدم Fine-grained Personal Access Token على حساب مالك مستودع القالب، مع صلاحيات:
- Administration: Read and write (لتحويل مستودع Ps4tools إلى Template وإنشاء مستودع منه).
- Contents: Read and write (لرفع ملفات المود).
- Actions: Read and write (لتشغيل Workflow).

لا تضع الرمز داخل ملفات المشروع. التطبيق يحفظه محليًا في Keychain.

## حدود الرفع

يرفع التطبيق الملفات عبر GitHub Contents API، وحد الملف الواحد 100 MB. الملفات الأكبر تحتاج مسار رفع بديلًا (Git LFS أو تخزين خارجي) قبل إضافتها إلى التطبيق.

## حالة التنفيذ

هذه نسخة أولية من واجهة iOS وربط GitHub. يجب أن ينجح بناء Xcode على GitHub Actions، ثم يلزم اختبار استيراد الملفات وتشغيل Workflow على جهاز iOS فعلي قبل اعتبار التطبيق جاهزًا للاستخدام الكامل.
