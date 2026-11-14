import Foundation

struct GitHubRepository: Decodable {
    let full_name: String
    let html_url: String
    let default_branch: String
}

enum GitHubClientError: LocalizedError {
    case invalidResponse
    case http(Int, String)
    case fileTooLarge
    case invalidRepositoryName

    var errorDescription: String? {
        switch self {
        case .invalidResponse: return "استجابة GitHub غير مفهومة."
        case .http(let code, let message): return "GitHub: (\(code)) \(message)"
        case .fileTooLarge: return "حجم الملف أكبر من حد GitHub Contents API وهو 100 MB."
        case .invalidRepositoryName: return "اسم المستودع غير صالح."
        }
    }
}

final class GitHubClient {
    private let base = URL(string: "https://api.github.com")!
    private let token: String

    init(token: String) { self.token = token }

    private func request(path: String, method: String, body: Data? = nil) async throws -> (Data, HTTPURLResponse) {
        var request = URLRequest(url: base.appending(path: path))
        request.httpMethod = method
        request.httpBody = body
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        request.setValue("2022-11-28", forHTTPHeaderField: "X-GitHub-Api-Version")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw GitHubClientError.invalidResponse }
        guard (200...299).contains(http.statusCode) else {
            let message = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["message"] as? String ?? "Unknown error"
            throw GitHubClientError.http(http.statusCode, message)
        }
        return (data, http)
    }

    func verify() async throws -> String {
        let (data, _) = try await request(path: "/user", method: "GET")
        let value = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        return value?["login"] as? String ?? "GitHub user"
    }

    func createRepository(name: String, isPrivate: Bool) async throws -> GitHubRepository {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_."))
        guard !name.isEmpty, name.unicodeScalars.allSatisfy({ allowed.contains($0) }) else {
            throw GitHubClientError.invalidRepositoryName
        }
        let body = try JSONSerialization.data(withJSONObject: [
            "name": name,
            "private": isPrivate,
            "auto_init": true,
            "description": "PS4 mod conversion workspace"
        ])
        let (data, _) = try await request(path: "/user/repos", method: "POST", body: body)
        return try JSONDecoder().decode(GitHubRepository.self, from: data)
    }

    func upload(fileURL: URL, repository: String, destination: String) async throws {
        let access = fileURL.startAccessingSecurityScopedResource()
        defer { if access { fileURL.stopAccessingSecurityScopedResource() } }
        let values = try fileURL.resourceValues(forKeys: [.fileSizeKey])
        if let size = values.fileSize, size > 100 * 1024 * 1024 { throw GitHubClientError.fileTooLarge }
        let data = try Data(contentsOf: fileURL)
        let body = try JSONSerialization.data(withJSONObject: [
            "message": "Upload mod input from PS4 Tools Mobile",
            "content": data.base64EncodedString()
        ])
        let encodedPath = destination.split(separator: "/").map { String($0).addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? String($0) }.joined(separator: "/")
        _ = try await request(path: "/repos/\(repository)/contents/\(encodedPath)", method: "PUT", body: body)
    }

    func runWorkflow(repository: String, workflow: String, branch: String, inputs: [String: String]) async throws {
        let body = try JSONSerialization.data(withJSONObject: ["ref": branch, "inputs": inputs])
        _ = try await request(path: "/repos/\(repository)/actions/workflows/\(workflow)/dispatches", method: "POST", body: body)
    }
}
