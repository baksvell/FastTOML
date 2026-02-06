#include "fasttoml/toml_parser.hpp"
#include <algorithm>
#include <cctype>
#include <ctime>
#include <limits>
#include <sstream>
#include <iomanip>
#include <regex>

#ifdef __AVX2__
#include <immintrin.h>
#endif

// Cross-platform count trailing zeros
#ifdef _MSC_VER
#include <intrin.h>
inline int ctz(unsigned int x) {
    unsigned long index;
    _BitScanForward(&index, x);
    return (int)index;
}
inline int ctz(unsigned long long x) {
    unsigned long index;
    _BitScanForward64(&index, x);
    return (int)index;
}
#else
inline int ctz(unsigned int x) {
    return __builtin_ctz(x);
}
inline int ctz(unsigned long long x) {
    return __builtin_ctzll(x);
}
#endif

namespace fasttoml {

// SIMD-optimized utility functions
namespace simd_utils {

inline bool is_whitespace(char c) {
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

inline bool is_whitespace_no_nl(char c) {
    return c == ' ' || c == '\t' || c == '\r';
}

#if defined(__AVX2__)
// AVX2-optimized skip whitespace
const char* skip_whitespace(const char* ptr, const char* end) {
    if (end - ptr < 32) {
        // Small buffer, use scalar code
        while (ptr < end && is_whitespace(*ptr)) {
            ++ptr;
        }
        return ptr;
    }
    
    // Process 32 bytes at a time with AVX2
    const __m256i space = _mm256_set1_epi8(' ');
    const __m256i tab = _mm256_set1_epi8('\t');
    const __m256i cr = _mm256_set1_epi8('\r');
    const __m256i nl = _mm256_set1_epi8('\n');
    
    while (end - ptr >= 32) {
        __m256i chunk = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(ptr));
        
        __m256i eq_space = _mm256_cmpeq_epi8(chunk, space);
        __m256i eq_tab = _mm256_cmpeq_epi8(chunk, tab);
        __m256i eq_cr = _mm256_cmpeq_epi8(chunk, cr);
        __m256i eq_nl = _mm256_cmpeq_epi8(chunk, nl);
        
        __m256i combined = _mm256_or_si256(
            _mm256_or_si256(eq_space, eq_tab),
            _mm256_or_si256(eq_cr, eq_nl)
        );
        
        unsigned int mask = static_cast<unsigned int>(_mm256_movemask_epi8(combined));
        if (mask != 0xFFFFFFFFU) {
            // Found non-whitespace
            int idx = ctz(~mask);
            return ptr + idx;
        }
        
        ptr += 32;
    }
    
    // Handle remaining bytes
    while (ptr < end && is_whitespace(*ptr)) {
        ++ptr;
    }
    
    return ptr;
}

// AVX2-optimized skip whitespace (no newlines)
const char* skip_whitespace_no_nl(const char* ptr, const char* end) {
    if (end - ptr < 32) {
        while (ptr < end && is_whitespace_no_nl(*ptr)) {
            ++ptr;
        }
        return ptr;
    }
    
    const __m256i space = _mm256_set1_epi8(' ');
    const __m256i tab = _mm256_set1_epi8('\t');
    const __m256i cr = _mm256_set1_epi8('\r');
    
    while (end - ptr >= 32) {
        __m256i chunk = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(ptr));
        
        __m256i eq_space = _mm256_cmpeq_epi8(chunk, space);
        __m256i eq_tab = _mm256_cmpeq_epi8(chunk, tab);
        __m256i eq_cr = _mm256_cmpeq_epi8(chunk, cr);
        
        __m256i combined = _mm256_or_si256(_mm256_or_si256(eq_space, eq_tab), eq_cr);
        
        unsigned int mask = static_cast<unsigned int>(_mm256_movemask_epi8(combined));
        if (mask != 0xFFFFFFFFU) {
            int idx = ctz(~mask);
            return ptr + idx;
        }
        
        ptr += 32;
    }
    
    while (ptr < end && is_whitespace_no_nl(*ptr)) {
        ++ptr;
    }
    
    return ptr;
}

// AVX2-optimized find character
const char* find_char_simd(const char* ptr, const char* end, char c) {
    if (end - ptr < 32) {
        while (ptr < end && *ptr != c) {
            ++ptr;
        }
        return ptr;
    }
    
    const __m256i target = _mm256_set1_epi8(c);
    
    while (end - ptr >= 32) {
        __m256i chunk = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(ptr));
        __m256i eq = _mm256_cmpeq_epi8(chunk, target);
        unsigned int mask = static_cast<unsigned int>(_mm256_movemask_epi8(eq));
        
        if (mask != 0) {
            int idx = ctz(mask);
            return ptr + idx;
        }
        
        ptr += 32;
    }
    
    while (ptr < end && *ptr != c) {
        ++ptr;
    }
    
    return ptr;
}

#else
// Fallback scalar implementations
const char* skip_whitespace(const char* ptr, const char* end) {
    while (ptr < end && is_whitespace(*ptr)) {
        ++ptr;
    }
    return ptr;
}

const char* skip_whitespace_no_nl(const char* ptr, const char* end) {
    while (ptr < end && is_whitespace_no_nl(*ptr)) {
        ++ptr;
    }
    return ptr;
}

const char* find_char_simd(const char* ptr, const char* end, char c) {
    while (ptr < end && *ptr != c) {
        ++ptr;
    }
    return ptr;
}
#endif

} // namespace simd_utils

// TomlParser implementation
TomlParser::TomlParser() : current_(nullptr), end_(nullptr) {
    root_table_ = std::make_shared<Table>();
    current_table_ = root_table_;
}

TomlParser::~TomlParser() = default;

// TOML 1.0: control chars U+0000-U+001F (except tab, LF, CR in CRLF) and U+007F are not permitted
static bool is_forbidden_control(char c) {
    unsigned char u = static_cast<unsigned char>(c);
    if (u == 0x09 || u == 0x0A) return false;  // tab, LF always allowed
    if (u == 0x0D) return false;  // CR allowed only in CRLF; checked separately
    if (u <= 0x1F || u == 0x7F) return true;
    return false;
}

std::shared_ptr<Table> TomlParser::parse(const std::string& input) {
    error_message_.clear();
    array_of_tables_paths_.clear();
    const size_t n = input.size();
    for (size_t i = 0; i < n; ++i) {
        unsigned char u = static_cast<unsigned char>(input[i]);
        if (u == 0x0D) {
            // CR only permitted as part of CRLF
            if (i + 1 >= n || input[i + 1] != '\n') {
                set_error("Control characters (U+0000-U+001F except tab/LF/CR in CRLF) and U+007F are not permitted");
                return nullptr;
            }
        } else if (is_forbidden_control(static_cast<char>(u))) {
            set_error("Control characters (U+0000-U+001F except tab/LF/CR in CRLF) and U+007F are not permitted");
            return nullptr;
        }
    }
    current_ = input.c_str();
    end_ = current_ + input.size();
    root_table_ = std::make_shared<Table>();
    current_table_ = root_table_;
    
    try {
        parse_document();
    } catch (const std::exception& e) {
        set_error(e.what());
        return nullptr;
    }
    
    if (has_error()) {
        return nullptr;
    }
    
    return root_table_;
}

void TomlParser::parse_document() {
    skip_whitespace();
    while (!eof()) {
        skip_whitespace();
        if (eof()) break;
        
        if (peek() == '#') {
            skip_comment();
            continue;
        }
        
        if (peek() == '[') {
            advance(); // '['
            skip_whitespace();
            
            bool is_array_of_tables = false;
            if (peek() == '[') {
                is_array_of_tables = true;
                advance();
                skip_whitespace();
            }
            
            std::vector<std::string> path = parse_dotted_key();
            if (path.empty()) {
                set_error("Empty table header");
                return;
            }
            
            skip_whitespace();
            if (is_array_of_tables) {
                expect_char(']');
                expect_char(']');
            } else {
                expect_char(']');
            }
            skip_whitespace();
            skip_comment();
            
            if (is_array_of_tables) {
                current_table_ = get_or_create_array_append_table(path);
                if (!current_table_) return;
            } else {
                current_table_ = get_or_create_table_at_path(path);
                if (!current_table_) return;
            }
            continue;
        }
        
        // Parse key-value pair (supports dotted keys: a.b.c = value)
        parse_key_value_pair(current_table_);
        skip_whitespace();
        
        if (!eof() && peek() != '#' && peek() != '[') {
            skip_whitespace();
        }
    }
}

void TomlParser::parse_key_value_pair(std::shared_ptr<Table> table) {
    std::vector<std::string> path = parse_dotted_key();
    if (path.empty()) return;
    skip_whitespace_no_nl();
    expect_char('=');
    skip_whitespace_no_nl();
    TomlValue value = parse_value();
    skip_whitespace_no_nl();
    skip_comment();
    set_value_at_path(table, path, value);
}

std::vector<std::string> TomlParser::parse_dotted_key() {
    std::vector<std::string> path;
    path.push_back(parse_key());
    skip_whitespace_no_nl();
    while (!eof() && peek() == '.') {
        advance(); // '.'
        skip_whitespace_no_nl();
        path.push_back(parse_key());
        skip_whitespace_no_nl();
    }
    return path;
}

std::shared_ptr<Table> TomlParser::get_or_create_table_at_path(const std::vector<std::string>& path) {
    std::shared_ptr<Table> t = root_table_;
    for (size_t i = 0; i < path.size(); ++i) {
        const std::string& key = path[i];
        if (t->has(key)) {
            TomlValue& v = t->values[key];
            if (std::holds_alternative<TablePtr>(v)) {
                t = std::get<TablePtr>(v);
            } else if (std::holds_alternative<ArrayPtr>(v)) {
                // [arr.subtab] only when arr is array-of-tables (from [[arr]]). Static array (a = [...]) cannot be extended.
                std::vector<std::string> path_so_far(path.begin(), path.begin() + static_cast<std::ptrdiff_t>(i) + 1);
                if (array_of_tables_paths_.find(path_so_far) == array_of_tables_paths_.end()) {
                    set_error("Cannot extend static array with table header");
                    return nullptr;
                }
                auto arr = std::get<ArrayPtr>(v);
                if (arr->elements.empty()) {
                    set_error("Array of tables is empty");
                    return nullptr;
                }
                auto& last = arr->elements.back();
                if (!std::holds_alternative<TablePtr>(last)) {
                    set_error("Key '" + key + "' already defined as non-table");
                    return nullptr;
                }
                t = std::get<TablePtr>(last);
            } else {
                set_error("Key '" + key + "' already defined as non-table");
                return nullptr;
            }
        } else {
            auto new_table = std::make_shared<Table>();
            t->set(key, new_table);
            t = new_table;
        }
    }
    return t;
}

std::shared_ptr<Table> TomlParser::get_or_create_array_append_table(const std::vector<std::string>& path) {
    if (path.empty()) {
        set_error("Empty array of tables path");
        return nullptr;
    }
    std::shared_ptr<Table> t = root_table_;
    for (size_t i = 0; i + 1 < path.size(); ++i) {
        const std::string& key = path[i];
        if (t->has(key)) {
            TomlValue& v = t->values[key];
            if (std::holds_alternative<TablePtr>(v)) {
                t = std::get<TablePtr>(v);
            } else if (std::holds_alternative<ArrayPtr>(v)) {
                std::vector<std::string> path_so_far(path.begin(), path.begin() + static_cast<std::ptrdiff_t>(i) + 1);
                if (array_of_tables_paths_.find(path_so_far) == array_of_tables_paths_.end()) {
                    set_error("Key '" + key + "' already defined as non-table");
                    return nullptr;
                }
                auto arr = std::get<ArrayPtr>(v);
                if (arr->elements.empty()) {
                    set_error("Array of tables is empty");
                    return nullptr;
                }
                auto& last = arr->elements.back();
                if (!std::holds_alternative<TablePtr>(last)) {
                    set_error("Key '" + key + "' already defined as non-array-of-tables");
                    return nullptr;
                }
                t = std::get<TablePtr>(last);
            } else {
                set_error("Key '" + key + "' already defined as non-table");
                return nullptr;
            }
        } else {
            auto new_table = std::make_shared<Table>();
            t->set(key, new_table);
            t = new_table;
        }
    }
    const std::string& last_key = path.back();
    if (!t->has(last_key)) {
        array_of_tables_paths_.insert(path);
        auto arr = std::make_shared<Array>();
        auto new_table = std::make_shared<Table>();
        arr->append(new_table);
        t->set(last_key, arr);
        return new_table;
    }
    TomlValue& v = t->values[last_key];
    if (!std::holds_alternative<ArrayPtr>(v)) {
        set_error("Key '" + last_key + "' already defined as non-array");
        return nullptr;
    }
    auto arr = std::get<ArrayPtr>(v);
    // [[key]] only allowed if key was created by a previous [[key]] (array-of-tables), not by key = [] (static array)
    if (array_of_tables_paths_.find(path) == array_of_tables_paths_.end()) {
        set_error("Key '" + last_key + "' already defined as non-array-of-tables");
        return nullptr;
    }
    for (const auto& elem : arr->elements) {
        if (!std::holds_alternative<TablePtr>(elem)) {
            set_error("Key '" + last_key + "' already defined as non-array-of-tables");
            return nullptr;
        }
    }
    auto new_table = std::make_shared<Table>();
    arr->append(new_table);
    return new_table;
}

void TomlParser::set_value_at_path(std::shared_ptr<Table> table, const std::vector<std::string>& path, const TomlValue& value) {
    if (path.empty()) return;
    std::shared_ptr<Table> t = table;
    for (size_t i = 0; i + 1 < path.size(); ++i) {
        const std::string& key = path[i];
        if (t->has(key)) {
            TomlValue& v = t->values[key];
            if (std::holds_alternative<TablePtr>(v)) {
                t = std::get<TablePtr>(v);
            } else {
                set_error("Key '" + key + "' already defined as non-table");
                return;
            }
        } else {
            auto new_table = std::make_shared<Table>();
            t->set(key, new_table);
            t = new_table;
        }
    }
    t->set(path.back(), value);
}


std::string TomlParser::parse_key() {
    skip_whitespace_no_nl();
    
    if (peek() == '"') {
        if (current_ + 2 < end_ && current_[1] == '"' && current_[2] == '"') {
            current_ += 3;
            return parse_multiline_basic_string();
        }
        return parse_basic_string();
    } else if (peek() == '\'') {
        if (current_ + 2 < end_ && current_[1] == '\'' && current_[2] == '\'') {
            current_ += 3;
            return parse_multiline_literal_string();
        }
        return parse_literal_string();
    } else {
        // Bare key
        std::string key;
        while (!eof() && (std::isalnum(peek()) || peek() == '_' || peek() == '-')) {
            key += advance();
        }
        if (key.empty()) {
            set_error("Expected key");
            // Consume one character to make progress and avoid infinite loop on invalid input
            if (!eof()) advance();
        }
        return key;
    }
}

TomlValue TomlParser::parse_value() {
    skip_whitespace_no_nl();
    
    char c = peek();
    
    if (c == '"') {
        if (current_ + 2 < end_ && current_[1] == '"' && current_[2] == '"') {
            current_ += 3;
            return parse_multiline_basic_string();
        }
        return parse_basic_string();
    } else if (c == '\'') {
        if (current_ + 2 < end_ && current_[1] == '\'' && current_[2] == '\'') {
            current_ += 3;
            return parse_multiline_literal_string();
        }
        return parse_literal_string();
    } else if (c == '[') {
        // Array
        return TomlValue(parse_array());
    } else if (c == '{') {
        return TomlValue(parse_inline_table());
    } else if (std::isdigit(c) || c == '+' || c == '-' || c == '.') {
        // Date/time or number: try datetime first if pattern matches
        if (std::isdigit(c) && static_cast<size_t>(end_ - current_) >= 10 &&
            std::isdigit(current_[0]) && std::isdigit(current_[1]) &&
            std::isdigit(current_[2]) && std::isdigit(current_[3]) &&
            current_[4] == '-') {
            auto dt = try_parse_datetime();
            if (dt) return *dt;
            if (has_error()) return Integer(0);
        }
        if (std::isdigit(c) && static_cast<size_t>(end_ - current_) >= 8 &&
            std::isdigit(current_[0]) && std::isdigit(current_[1]) &&
            current_[2] == ':') {
            auto dt = try_parse_datetime();
            if (dt) return *dt;
            if (has_error()) return Integer(0);
        }
        // Number (or special float +inf, -inf, +nan, -nan) or integer 0x/0o/0b
        const char* start = current_;
        bool has_dot = false;
        bool has_exp = false;
        
        if (c == '+' || c == '-') {
            advance();
            if (!eof() && peek() == 'i' && end_ - current_ >= 3 && current_[0] == 'i' && current_[1] == 'n' && current_[2] == 'f' &&
                (current_ + 3 >= end_ || !(std::isalnum(current_[3]) || current_[3] == '_'))) {
                current_ += 3;
                double v = (*start == '-') ? -std::numeric_limits<double>::infinity() : std::numeric_limits<double>::infinity();
                return TomlValue(Float(v));
            }
            if (!eof() && peek() == 'n' && end_ - current_ >= 3 && current_[0] == 'n' && current_[1] == 'a' && current_[2] == 'n' &&
                (current_ + 3 >= end_ || !(std::isalnum(current_[3]) || current_[3] == '_'))) {
                current_ += 3;
                double v = (*start == '-') ? -std::numeric_limits<double>::quiet_NaN() : std::numeric_limits<double>::quiet_NaN();
                return TomlValue(Float(v));
            }
        }
        
        // Integer literals: 0x hex, 0o octal, 0b binary (with optional leading +/-)
        if (current_ < end_ && *current_ == '0' && current_ + 2 <= end_) {
            char n = current_[1];
            int base = 0;
            if (n == 'x' || n == 'X') base = 16;
            else if (n == 'o' || n == 'O') base = 8;
            else if (n == 'b' || n == 'B') base = 2;
            if (base != 0) {
                current_ += 2;
                std::string num_clean;
                auto is_hex = [](char ch) { return std::isdigit(ch) || (ch >= 'a' && ch <= 'f') || (ch >= 'A' && ch <= 'F'); };
                auto is_oct = [](char ch) { return ch >= '0' && ch <= '7'; };
                auto is_bin = [](char ch) { return ch == '0' || ch == '1'; };
                while (!eof() && (peek() == '_' || (base == 16 && is_hex(peek())) || (base == 8 && is_oct(peek())) || (base == 2 && is_bin(peek())))) {
                    if (peek() != '_') num_clean += advance();
                    else advance();
                }
                if (num_clean.empty()) {
                    set_error("Invalid integer literal");
                    return Integer(0);
                }
                try {
                    Integer v = static_cast<Integer>(std::stoll(num_clean, nullptr, base));
                    if (start < end_ && *start == '-') v = -v;
                    return TomlValue(v);
                } catch (...) {
                    set_error("Invalid integer: " + std::string(start, current_));
                    return Integer(0);
                }
            }
        }
        // Leading dot (e.g. .1) or leading zero in decimal (e.g. 09) invalid
        if (current_ == start && peek() == '.') {
            set_error("Leading dot not allowed in number");
            return Float(0.0);
        }
        if (current_ == start && peek() == '0' && current_ + 1 < end_ && std::isdigit(current_[1])) {
            set_error("Leading zero not allowed in decimal integer");
            return Integer(0);
        }
        while (!eof() && (std::isdigit(peek()) || peek() == '.' || peek() == 'e' || peek() == 'E' || peek() == '+' || peek() == '-' || peek() == '_')) {
            if (peek() == '.') {
                if (has_dot) {
                    set_error("Double dot not allowed in float");
                    return Float(0.0);
                }
                has_dot = true;
            }
            if (peek() == 'e' || peek() == 'E') has_exp = true;
            advance();
        }
        
        std::string num_str(start, current_);
        if (has_dot && !has_exp && !num_str.empty() && num_str.back() == '.') {
            set_error("Trailing dot not allowed in float");
            return Float(0.0);
        }
        std::string num_clean;
        for (char ch : num_str) if (ch != '_') num_clean += ch;
        if (has_dot || has_exp) {
            try {
                return Float(std::stod(num_clean));
            } catch (...) {
                set_error("Invalid float: " + num_str);
                return Float(0.0);
            }
        } else {
            try {
                return Integer(std::stoll(num_clean));
            } catch (...) {
                set_error("Invalid integer: " + num_str);
                return Integer(0);
            }
        }
    } else if (c == 't' || c == 'f') {
        // Boolean
        return parse_boolean();
    } else if (c == 'i' && end_ - current_ >= 3 && current_[0] == 'i' && current_[1] == 'n' && current_[2] == 'f' &&
               (current_ + 3 >= end_ || !(std::isalnum(current_[3]) || current_[3] == '_'))) {
        current_ += 3;
        return TomlValue(Float(std::numeric_limits<double>::infinity()));
    } else if (c == 'n' && end_ - current_ >= 3 && current_[0] == 'n' && current_[1] == 'a' && current_[2] == 'n' &&
               (current_ + 3 >= end_ || !(std::isalnum(current_[3]) || current_[3] == '_'))) {
        current_ += 3;
        return TomlValue(Float(std::numeric_limits<double>::quiet_NaN()));
    } else {
        set_error("Unexpected character in value: " + std::string(1, c));
        return Integer(0);
    }
}

String TomlParser::parse_string() {
    if (peek() == '"') {
        return parse_basic_string();
    } else {
        return parse_literal_string();
    }
}

String TomlParser::parse_basic_string() {
    expect_char('"');
    std::string result;
    
    while (!eof() && peek() != '"') {
        if (peek() == '\\') {
            advance(); // skip '\'
            result += parse_escape_sequence();
        } else {
            result += advance();
        }
    }
    
    expect_char('"');
    return result;
}

String TomlParser::parse_literal_string() {
    expect_char('\'');
    std::string result;
    
    while (!eof() && peek() != '\'') {
        result += advance();
    }
    
    expect_char('\'');
    return result;
}

String TomlParser::parse_multiline_basic_string() {
    // Opening """ already consumed. Trim first newline if present.
    if (!eof() && peek() == '\n') advance();
    std::string result;
    while (!eof()) {
        if (peek() == '"') {
            int n = 0;
            while (!eof() && peek() == '"') { advance(); n++; }
            if (n >= 3) {
                for (int i = 0; i < n - 3; i++) result += '"';
                // Close only if exactly 3 quotes, or next char is newline/eof (end of value)
                if (n == 3 || eof() || peek() == '\n' || peek() == '\r') return result;
            } else {
                for (int i = 0; i < n; i++) result += '"';
            }
        } else if (peek() == '\\') {
            advance();
            result += parse_escape_sequence();
        } else {
            result += advance();
        }
    }
    set_error("Unclosed multiline basic string");
    return result;
}

String TomlParser::parse_multiline_literal_string() {
    // Opening ''' already consumed. Trim first newline if present.
    if (!eof() && peek() == '\n') advance();
    std::string result;
    while (!eof()) {
        if (peek() == '\'') {
            int n = 0;
            while (!eof() && peek() == '\'') { advance(); n++; }
            if (n >= 3) {
                for (int i = 0; i < n - 3; i++) result += '\'';
                if (n == 3 || eof() || peek() == '\n' || peek() == '\r') return result;
            } else {
                for (int i = 0; i < n; i++) result += '\'';
            }
        } else {
            result += advance();
        }
    }
    set_error("Unclosed multiline literal string");
    return result;
}

Integer TomlParser::parse_integer() {
    std::string num_str;
    if (peek() == '+' || peek() == '-') {
        num_str += advance();
    }
    
    while (!eof() && std::isdigit(peek())) {
        num_str += advance();
    }
    
    try {
        return Integer(std::stoll(num_str));
    } catch (...) {
        set_error("Invalid integer: " + num_str);
        return Integer(0);
    }
}

Float TomlParser::parse_float() {
    std::string num_str;
    if (peek() == '+' || peek() == '-') {
        num_str += advance();
    }
    
    while (!eof() && (std::isdigit(peek()) || peek() == '.' || peek() == 'e' || peek() == 'E')) {
        num_str += advance();
    }
    
    try {
        return Float(std::stod(num_str));
    } catch (...) {
        set_error("Invalid float: " + num_str);
        return Float(0.0);
    }
}

Boolean TomlParser::parse_boolean() {
    if (peek() == 't') {
        expect_char('t');
        expect_char('r');
        expect_char('u');
        expect_char('e');
        return true;
    } else {
        expect_char('f');
        expect_char('a');
        expect_char('l');
        expect_char('s');
        expect_char('e');
        return false;
    }
}

TablePtr TomlParser::parse_inline_table() {
    expect_char('{');
    skip_whitespace_no_nl();
    auto table = std::make_shared<Table>();
    if (peek() == '}') {
        advance();
        return table;
    }
    while (!eof()) {
        std::vector<std::string> path = parse_dotted_key();
        if (path.empty()) break;
        skip_whitespace_no_nl();
        expect_char('=');
        skip_whitespace_no_nl();
        TomlValue value = parse_value();
        set_value_at_path(table, path, value);
        skip_whitespace_no_nl();
        if (peek() == '}') break;
        expect_char(',');
        skip_whitespace_no_nl();
    }
    expect_char('}');
    return table;
}

static bool parse_int(const char*& ptr, const char* end, int min_digits, int max_digits, int64_t& out) {
    if (ptr >= end || !std::isdigit(*ptr)) return false;
    int64_t v = 0;
    int n = 0;
    while (ptr < end && n < max_digits && std::isdigit(*ptr)) {
        v = v * 10 + (*ptr - '0');
        ++ptr;
        ++n;
    }
    if (n < min_digits) return false;
    out = v;
    return true;
}

// True if character can follow a date/time value (TOML value terminator).
static bool is_value_terminator(char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == ',' || c == ']' || c == '}' || c == '#';
}

// Max day in month (1-12); leap year for February.
static int max_day_in_month(int64_t year, int64_t month) {
    static const int days_in_month[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    int maxd = days_in_month[month - 1];
    if (month == 2 && (year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)))
        maxd = 29;
    return maxd;
}

// Portable: days from 1970-01-01 to (y, m, d). y full year, m 1-12, d 1-31.
static int days_from_1970(int y, int m, int d) {
    static const int days_in_month[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    int days = 0;
    for (int yy = 1970; yy < y; ++yy)
        days += (yy % 4 == 0 && (yy % 100 != 0 || yy % 400 == 0)) ? 366 : 365;
    for (int mm = 0; mm < m - 1; ++mm)
        days += days_in_month[mm];
    if (m > 2 && (y % 4 == 0 && (y % 100 != 0 || y % 400 == 0)))
        days += 1;
    days += d - 1;
    return days;
}

static std::time_t tm_to_time_t_utc(const std::tm& tm) {
    int days = days_from_1970(tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday);
    return static_cast<std::time_t>(days) * 86400 +
           tm.tm_hour * 3600 + tm.tm_min * 60 + tm.tm_sec;
}

std::optional<TomlValue> TomlParser::try_parse_datetime() {
    const char* start = current_;
    // Date: YYYY-MM-DD or datetime: YYYY-MM-DDTHH:MM:SS or with offset
    if (end_ - current_ >= 10 &&
        std::isdigit(current_[0]) && std::isdigit(current_[1]) &&
        std::isdigit(current_[2]) && std::isdigit(current_[3]) &&
        current_[4] == '-' && std::isdigit(current_[5]) && std::isdigit(current_[6]) &&
        current_[7] == '-' && std::isdigit(current_[8]) && std::isdigit(current_[9])) {
        const char* p = current_;
        int64_t year, month, day;
        if (!parse_int(p, end_, 4, 4, year)) { current_ = start; return std::nullopt; }
        if (p >= end_ || *p != '-') { current_ = start; return std::nullopt; }
        ++p;
        if (!parse_int(p, end_, 2, 2, month) || month < 1 || month > 12) {
            set_error("Invalid date: month must be 01-12");
            current_ = start;
            return std::nullopt;
        }
        if (p >= end_ || *p != '-') { current_ = start; return std::nullopt; }
        ++p;
        if (!parse_int(p, end_, 2, 2, day) || day < 1 || day > 31) {
            set_error("Invalid date: day must be 01-31");
            current_ = start;
            return std::nullopt;
        }
        if (day > max_day_in_month(year, month)) {
            set_error("Invalid date: day out of range for month");
            current_ = start;
            return std::nullopt;
        }
        if (p == end_) {
            current_ = p;
            return TomlValue(String(start, p));
        }
        if (*p == ' ') {
            // Date only if not followed by HH:MM:SS
            if (end_ - p < 9) { current_ = p; return TomlValue(String(start, p)); }
            const char* q = p + 1;
            if (!(end_ - q >= 8 && std::isdigit(q[0]) && std::isdigit(q[1]) && q[2] == ':' &&
                  std::isdigit(q[3]) && std::isdigit(q[4]) && q[5] == ':' && std::isdigit(q[6]) && std::isdigit(q[7]))) {
                current_ = p;
                return TomlValue(String(start, p));
            }
            ++p;
        } else if (*p == 'T' || *p == 't') {
            ++p;
        } else {
            // Date only: must not have trailing garbage (e.g. 1979-01-01x)
            if (p < end_ && !is_value_terminator(*p)) {
                set_error("Invalid date: unexpected character after date");
                current_ = start;
                return std::nullopt;
            }
            current_ = p;
            return TomlValue(String(start, start + 10));
        }
        if (end_ - p >= 8) {
            int64_t hour, minute, second = 0;
            if (!parse_int(p, end_, 2, 2, hour) || hour > 23) {
                set_error("Invalid datetime: hour must be 00-23");
                current_ = start;
                return std::nullopt;
            }
            if (p >= end_ || *p != ':') { current_ = start; return std::nullopt; }
            ++p;
            if (!parse_int(p, end_, 2, 2, minute) || minute > 59) {
                set_error("Invalid datetime: minute must be 00-59");
                current_ = start;
                return std::nullopt;
            }
            if (p >= end_ || *p != ':') { current_ = start; return std::nullopt; }
            ++p;
            if (!parse_int(p, end_, 2, 2, second) || second > 60) {
                set_error("Invalid datetime: second must be 00-60");
                current_ = start;
                return std::nullopt;
            }
            double subsecond = 0.0;
            if (p < end_ && *p == '.') {
                ++p;
                const char* frac_start = p;
                while (p < end_ && std::isdigit(*p)) ++p;
                if (p == frac_start) {
                    set_error("Invalid datetime: fractional seconds must have at least one digit");
                    current_ = start;
                    return std::nullopt;
                }
                std::string frac(frac_start, p);
                subsecond = std::stod("0." + frac);
            }
            int offset_minutes = 0;
            bool has_offset = false;
            if (p < end_ && (*p == 'Z' || *p == 'z')) {
                ++p;
                has_offset = true;
            } else if (p + 1 < end_ && (*p == '+' || *p == '-')) {
                const char* offset_start = p;
                char sign = *p++;
                int64_t oh, om;
                if (parse_int(p, end_, 2, 2, oh) && oh <= 23 && p < end_ && *p == ':' &&
                    parse_int(++p, end_, 2, 2, om) && om <= 59) {
                    offset_minutes = static_cast<int>((oh * 60 + om) * (sign == '-' ? -1 : 1));
                    has_offset = true;
                } else {
                    set_error("Invalid datetime: offset must be Z or ±HH:MM");
                    current_ = start;
                    return std::nullopt;
                }
            }
            using namespace std::chrono;
            std::tm tm = {};
            tm.tm_year = static_cast<int>(year - 1900);
            tm.tm_mon = static_cast<int>(month - 1);
            tm.tm_mday = static_cast<int>(day);
            tm.tm_hour = static_cast<int>(hour);
            tm.tm_min = static_cast<int>(minute);
            tm.tm_sec = static_cast<int>(second);
            tm.tm_isdst = 0;
            std::time_t t = tm_to_time_t_utc(tm);
            if (t < 0) { current_ = start; return std::nullopt; }
            system_clock::time_point tp = system_clock::from_time_t(t) +
                duration_cast<system_clock::duration>(duration<double>(subsecond));
            if (has_offset) {
                current_ = p;
                // Years outside time_t range: return as string for correct tagged output
                if (year < 1970 || year > 2037) {
                    std::string raw(start, p);
                    if (raw.size() >= 19 && raw[10] == ' ') raw[10] = 'T';
                    return TomlValue(raw);
                }
                tp -= minutes(offset_minutes);
                return TomlValue(DateTimeOffset{tp, offset_minutes});
            }
            // Local datetime (no offset): preserve as string; reject trailing garbage
            if (p < end_ && !is_value_terminator(*p)) {
                set_error("Invalid datetime: unexpected character after time");
                current_ = start;
                return std::nullopt;
            }
            current_ = p;
            return TomlValue(String(start, p));
        }
        if (p < end_ && !is_value_terminator(*p)) {
            set_error("Invalid date: unexpected character after date");
            current_ = start;
            return std::nullopt;
        }
        current_ = p;
        return TomlValue(String(start, p));
    }
    // Time only: HH:MM:SS or HH:MM:SS.frac
    if (end_ - current_ >= 8 &&
        std::isdigit(current_[0]) && std::isdigit(current_[1]) &&
        current_[2] == ':' && std::isdigit(current_[3]) && std::isdigit(current_[4]) &&
        current_[5] == ':' && std::isdigit(current_[6]) && std::isdigit(current_[7])) {
        const char* p = current_;
        int64_t h, m, s;
        if (!parse_int(p, end_, 2, 2, h) || h > 23) {
            set_error("Invalid time: hour must be 00-23");
            current_ = start;
            return std::nullopt;
        }
        if (p >= end_ || *p != ':') { current_ = start; return std::nullopt; }
        ++p;
        if (!parse_int(p, end_, 2, 2, m) || m > 59) {
            set_error("Invalid time: minute must be 00-59");
            current_ = start;
            return std::nullopt;
        }
        if (p >= end_ || *p != ':') { current_ = start; return std::nullopt; }
        ++p;
        if (!parse_int(p, end_, 2, 2, s) || s > 60) {
            set_error("Invalid time: second must be 00-60");
            current_ = start;
            return std::nullopt;
        }
        if (p < end_ && *p == '.') {
            ++p;
            while (p < end_ && std::isdigit(*p)) ++p;
        }
        if (p < end_ && !is_value_terminator(*p)) {
            set_error("Invalid time: unexpected character after time");
            current_ = start;
            return std::nullopt;
        }
        current_ = p;
        return TomlValue(String(start, p));
    }
    return std::nullopt;
}

DateTime TomlParser::parse_datetime() {
    auto v = try_parse_datetime();
    if (v && std::holds_alternative<DateTime>(*v))
        return std::get<DateTime>(*v);
    set_error("Expected datetime");
    return std::chrono::system_clock::now();
}

ArrayPtr TomlParser::parse_array() {
    expect_char('[');
    skip_whitespace();
    skip_comment();
    
    auto array = std::make_shared<Array>();
    
    if (peek() == ']') {
        advance();
        return array;
    }
    
    while (!eof()) {
        for (;;) {
            skip_whitespace();
            if (peek() == ']') goto end_array_loop;
            if (peek() == '#') { skip_comment(); continue; }
            break;
        }
        
        TomlValue value = parse_value();
        array->append(value);
        
        skip_whitespace();
        skip_comment();
        skip_whitespace();
        if (peek() == ',') {
            advance();
            skip_whitespace();
            skip_comment();
        } else if (peek() != ']') {
            set_error("Expected ',' or ']' in array");
            break;
        }
    }
end_array_loop:
    expect_char(']');
    return array;
}

std::string TomlParser::parse_escape_sequence() {
    if (eof()) {
        set_error("Unexpected end of string in escape sequence");
        return "";
    }
    char c = advance();
    switch (c) {
        case 'b': return "\b";
        case 't': return "\t";
        case 'n': return "\n";
        case 'f': return "\f";
        case 'r': return "\r";
        case '"': return "\"";
        case '\\': return "\\";
        case 'u': return parse_unicode_escape(4);
        case 'U': return parse_unicode_escape(8);
        default: {
            set_error("Invalid escape sequence in string: \\" + std::string(1, c) +
                      " (allowed: \\b \\t \\n \\f \\r \\\" \\\\ \\uXXXX \\UXXXXXXXX)");
            return "";
        }
    }
}

// Append UTF-8 encoding of codepoint to string. Returns false if codepoint invalid.
static bool append_utf8(std::string& out, uint32_t cp) {
    if (cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF))
        return false;
    if (cp <= 0x7F) {
        out += static_cast<char>(cp);
    } else if (cp <= 0x7FF) {
        out += static_cast<char>(0xC0 | (cp >> 6));
        out += static_cast<char>(0x80 | (cp & 0x3F));
    } else if (cp <= 0xFFFF) {
        out += static_cast<char>(0xE0 | (cp >> 12));
        out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
        out += static_cast<char>(0x80 | (cp & 0x3F));
    } else {
        out += static_cast<char>(0xF0 | (cp >> 18));
        out += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
        out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
        out += static_cast<char>(0x80 | (cp & 0x3F));
    }
    return true;
}

static int hex_digit(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

std::string TomlParser::parse_unicode_escape(int num_hex_digits) {
    uint32_t cp = 0;
    int i = 0;
    for (; i < num_hex_digits && !eof(); ++i) {
        int d = hex_digit(peek());
        if (d < 0) {
            set_error("Invalid hex digit in Unicode escape");
            return "\xEF\xBF\xBD";
        }
        advance();
        cp = (cp << 4) | static_cast<uint32_t>(d);
    }
    if (i != num_hex_digits) {
        set_error("Unicode escape truncated");
        return "\xEF\xBF\xBD";
    }
    if (cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) {
        set_error("Invalid Unicode codepoint in escape");
        return "\xEF\xBF\xBD";
    }
    std::string out;
    append_utf8(out, cp);
    return out;
}

void TomlParser::skip_whitespace() {
    current_ = simd_utils::skip_whitespace(current_, end_);
}

void TomlParser::skip_whitespace_no_nl() {
    current_ = simd_utils::skip_whitespace_no_nl(current_, end_);
}

void TomlParser::skip_comment() {
    if (peek() == '#') {
        while (!eof() && peek() != '\n') {
            advance();
        }
    }
}

void TomlParser::expect_char(char c) {
    if (eof() || peek() != c) {
        set_error("Expected '" + std::string(1, c) + "' but found '" + (eof() ? std::string("EOF") : std::string(1, peek())) + "'");
        return;
    }
    advance();
}

bool TomlParser::peek_char(char c) {
    return !eof() && peek() == c;
}

char TomlParser::peek() {
    if (eof()) return '\0';
    return *current_;
}

char TomlParser::advance() {
    if (eof()) return '\0';
    return *current_++;
}

bool TomlParser::eof() {
    return current_ >= end_;
}

void TomlParser::set_error(const std::string& message) {
    if (error_message_.empty()) {
        error_message_ = message;
    }
}

} // namespace fasttoml
