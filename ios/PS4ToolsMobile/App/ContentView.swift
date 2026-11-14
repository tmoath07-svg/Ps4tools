import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @AppStorage("github_pat") private var token = ""
    @State private var username = ""
    @State private var repoName = "ps4-mod-workspace"
    @State private var repository = ""
    @State private var selectedFiles: [URL] = []
    @State private var mode = "فحص الأدوات"
    @State private var isPrivate = true
    @State private var showingImporter = false
    @State private var showingGuide = false
    @State private var busy = false
    @State private var status = "اربط GitHub للبدء."
    @State private var errorText = ""

    private let modes = [
        "فحص الأدوات",
        "تحويل ملفات PC إلى PS4",
        "تحويل سيارة إلى DLC للسوني",
        "تحويل الملفات وبناء RPF",
        "تحويل DLC الكمبيوتر إلى DLC السوني",
        "تحويل مود FiveM متعدد السيارات إلى DLC للسوني",
        "تحويل YFT وYTD وبناء DLC متعدد السيارات للسوني",
        "استخراج الصور من YTD",
        "فك ملفات RPF",
        "بناء ملف RPF"
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header
                    GroupBox("حساب GitHub") {
                        VStack(alignment: .leading, spacing: 10) {
                            SecureField("GitHub Personal Access Token", text: $token)
                                .textInputAutocapitalization(.never)
                                .autocorrectionDisabled()
                            HStack {
                                Button("التحقق من الحساب") { Task { await verifyAccount() } }
                                    .buttonStyle(.borderedProminent)
                                    .disabled(token.isEmpty || busy)
                                if !username.isEmpty { Text("@\(username)").foregroundStyle(.green) }
                            }
                            Text("استخدم Token بصلاحيات Contents وActions وAdministration لإنشاء المستودعات وتشغيل Workflow.")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    GroupBox("مشروع GitHub") {
                        VStack(alignment: .leading, spacing: 10) {
                            TextField("اسم المستودع", text: $repoName)
                                .textInputAutocapitalization(.never)
                                .autocorrectionDisabled()
                            Toggle("مستودع خاص", isOn: $isPrivate)
                            Button("إنشاء مستودع جديد") { Task { await createRepository() } }
                                .buttonStyle(.borderedProminent)
                                .disabled(token.isEmpty || busy)
                            if !repository.isEmpty {
                                Text("المستودع: \(repository)").font(.caption).textSelection(.enabled)
                            }
                        }
                    }
                    GroupBox("ملفات المود") {
                        VStack(alignment: .leading, spacing: 10) {
                            Button {
                                showingImporter = true
                            } label: {
                                Label("اختيار ملفات من تطبيق الملفات", systemImage: "folder")
                            }
                            .buttonStyle(.bordered)
                            Text("عدد الملفات المختارة: \(selectedFiles.count)")
                                .font(.caption).foregroundStyle(.secondary)
                            ForEach(selectedFiles, id: \.absoluteString) { file in
                                Label(file.lastPathComponent, systemImage: "doc")
                                    .font(.caption).lineLimit(1)
                            }
                            Button("رفع الملفات إلى المستودع") { Task { await uploadFiles() } }
                                .buttonStyle(.borderedProminent)
                                .disabled(repository.isEmpty || selectedFiles.isEmpty || busy)
                        }
                    }
                    GroupBox("عملية التحويل") {
                        VStack(alignment: .leading, spacing: 10) {
                            Picker("نوع العملية", selection: $mode) {
                                ForEach(modes, id: \.self) { Text($0).tag($0) }
                            }
                            .pickerStyle(.menu)
                            Button("تشغيل التحويل على GitHub Actions") { Task { await startWorkflow() } }
                                .buttonStyle(.borderedProminent)
                                .disabled(repository.isEmpty || busy)
                        }
                    }
                    GroupBox("الحالة") {
                        Text(status).frame(maxWidth: .infinity, alignment: .leading)
                        if !errorText.isEmpty {
                            Text(errorText).foregroundStyle(.red).font(.caption)
                        }
                        if busy { ProgressView().frame(maxWidth: .infinity) }
                    }
                    Button("شرح الاستخدام") { showingGuide = true }
                        .buttonStyle(.bordered)
                        .frame(maxWidth: .infinity)
                }
                .padding()
            }
            .navigationTitle("PS4 TOOLS MOBILE")
            .sheet(isPresented: $showingGuide) { GuideView() }
            .fileImporter(isPresented: $showingImporter, allowedContentTypes: [.item], allowsMultipleSelection: true) { result in
                switch result {
                case .success(let urls):
                    selectedFiles = urls
                    status = "تم اختيار \(urls.count) ملف."
                case .failure(let error):
                    errorText = error.localizedDescription
                }
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("PS4 MOD CONVERTER").font(.title2.bold())
            Text("ارفع المود، اختر العملية، وخلي GitHub ينفذ البناء.")
                .foregroundStyle(.secondary)
        }
    }

    private func client() -> GitHubClient { GitHubClient(token: token.trimmingCharacters(in: .whitespacesAndNewlines)) }

    @MainActor private func verifyAccount() async {
        await perform {
            username = try await client().verify()
            status = "تم ربط GitHub بنجاح."
        }
    }

    @MainActor private func createRepository() async {
        await perform {
            let repo = try await client().createRepository(name: repoName, isPrivate: isPrivate)
            repository = repo.full_name
            status = "تم إنشاء المستودع: \(repo.html_url)"
        }
    }

    @MainActor private func uploadFiles() async {
        await perform {
            guard !repository.isEmpty else { return }
            for (index, file) in selectedFiles.enumerated() {
                status = "رفع الملف \(index + 1) من \(selectedFiles.count): \(file.lastPathComponent)"
                let destination = "input/\(file.lastPathComponent)"
                try await client().upload(fileURL: file, repository: repository, destination: destination)
            }
            status = "اكتمل رفع الملفات. تقدر تشغل التحويل."
        }
    }

    @MainActor private func startWorkflow() async {
        await perform {
            try await client().runWorkflow(
                repository: repository,
                workflow: "zokii-studio-dlc-fixed.yml",
                branch: "main",
                inputs: [
                    "mode": mode,
                    "toolkit_zip": "ZokiiStudio-Toolkit-FIXED.zip",
                    "release_tag": "",
                    "url": "",
                    "input_folder": "input",
                    "vehicle_spawn_name": "buccaneer2"
                ]
            )
            status = "تم إرسال طلب التشغيل إلى GitHub Actions. افتح تبويب Actions لمتابعة النتيجة."
        }
    }

    @MainActor private func perform(_ operation: () async throws -> Void) async {
        guard !busy else { return }
        busy = true
        errorText = ""
        defer { busy = false }
        do { try await operation() }
        catch { errorText = error.localizedDescription }
    }
}

struct GuideView: View {
    var body: some View {
        NavigationStack {
            List {
                Section("البدء") {
                    Text("1. أنشئ GitHub Personal Access Token من حسابك.")
                    Text("2. الصق الرمز في خانة GitHub واضغط التحقق.")
                    Text("3. اكتب اسم المستودع وأنشئه.")
                }
                Section("الملفات والتحويل") {
                    Text("4. اختر ملفات المود من تطبيق الملفات.")
                    Text("5. ارفع الملفات إلى مجلد input داخل المستودع.")
                    Text("6. اختر نوع العملية ثم شغّل GitHub Actions.")
                    Text("7. حمّل النتائج من Artifacts في صفحة Actions.")
                }
                Section("ملاحظات مهمة") {
                    Text("الملفات الفردية الأكبر من 100 MB لا يمكن رفعها عبر واجهة GitHub Contents API المستخدمة هنا.")
                    Text("إنشاء المستودع يحتاج صلاحية Administration، وتشغيل Workflow يحتاج صلاحية Actions.")
                    Text("لا تشارك Token مع أي شخص. يتم حفظه محليًا في إعدادات التطبيق.")
                }
            }
            .navigationTitle("شرح التطبيق")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
