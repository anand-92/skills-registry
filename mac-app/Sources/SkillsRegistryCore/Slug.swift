import Foundation

/// Normalize a skill name into a filesystem-safe registry slug.
///
/// Identical algorithm to `scan.Slugify` (Go) and `slugify` (Python):
/// lowercase, trim, replace every run of non-`[a-z0-9]` chars with `_`,
/// strip leading/trailing `_`, falling back to "skill" when empty.
public func slugify(_ name: String) -> String {
    let lowered = name.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    var out = ""
    out.reserveCapacity(lowered.count)
    var pendingUnderscore = false
    for ch in lowered.unicodeScalars {
        if (ch >= "a" && ch <= "z") || (ch >= "0" && ch <= "9") {
            if pendingUnderscore && !out.isEmpty {
                out.append("_")
            }
            pendingUnderscore = false
            out.unicodeScalars.append(ch)
        } else {
            pendingUnderscore = true
        }
    }
    // Trailing run collapses to nothing (matches Python's `.strip("_")`).
    if out.isEmpty { return "skill" }
    return out
}

/// Reduce a name or slug to a comparison key.
///
/// Lowercases and strips every non-alphanumeric character, so separator- and
/// case-only variants of one skill ("simplify-swarm", "simplify_swarm",
/// "Simplify Swarm") collapse to a single key ("simplifyswarm").
///
/// Comparison counterpart to `slugify`: `slugify` keeps word separators as
/// underscores to build a readable, filesystem-safe slug, while this removes
/// them entirely so two identifiers can be tested for "same skill" regardless
/// of which separator/case convention each used. Mirrors
/// `scan.NormalizeForMatch` in the Go CLI; keep the two in sync.
public func normalizeForMatch(_ s: String) -> String {
    let lowered = s.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    var out = ""
    out.reserveCapacity(lowered.count)
    for ch in lowered.unicodeScalars {
        if (ch >= "a" && ch <= "z") || (ch >= "0" && ch <= "9") {
            out.unicodeScalars.append(ch)
        }
    }
    return out
}
