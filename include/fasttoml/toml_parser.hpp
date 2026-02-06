#pragma once

#include <string>
#include <variant>
#include <vector>
#include <unordered_map>
#include <memory>
#include <optional>
#include <cstdint>
#include <chrono>
#include <set>

namespace fasttoml {

// Forward declarations
class Value;
class Table;
class Array;

// TOML value types
using Integer = int64_t;
using Float = double;
using Boolean = bool;
using String = std::string;
using DateTime = std::chrono::system_clock::time_point;
// Datetime with timezone offset (for correct RFC 3339 output in tagged JSON)
struct DateTimeOffset {
    DateTime utc;
    int offset_minutes;
};
using TablePtr = std::shared_ptr<Table>;
using ArrayPtr = std::shared_ptr<Array>;

// TOML value variant
using TomlValue = std::variant<
    Integer,
    Float,
    Boolean,
    String,
    DateTime,
    DateTimeOffset,
    TablePtr,
    ArrayPtr
>;

// TOML Table (key-value pairs)
class Table {
public:
    std::unordered_map<std::string, TomlValue> values;
    
    template<typename T>
    std::optional<T> get(const std::string& key) const {
        auto it = values.find(key);
        if (it == values.end()) {
            return std::nullopt;
        }
        try {
            return std::get<T>(it->second);
        } catch (...) {
            return std::nullopt;
        }
    }
    
    void set(const std::string& key, const TomlValue& value) {
        values[key] = value;
    }
    
    bool has(const std::string& key) const {
        return values.find(key) != values.end();
    }
};

// TOML Array
class Array {
public:
    std::vector<TomlValue> elements;
    
    void append(const TomlValue& value) {
        elements.push_back(value);
    }
    
    size_t size() const {
        return elements.size();
    }
};

// SIMD-optimized utility functions
namespace simd_utils {
    // Skip whitespace characters (space, tab, \r, \n)
    const char* skip_whitespace(const char* ptr, const char* end);
    
    // Skip whitespace except newlines
    const char* skip_whitespace_no_nl(const char* ptr, const char* end);
    
    // Find next character using SIMD
    const char* find_char_simd(const char* ptr, const char* end, char c);
    
    // Check if string is whitespace
    bool is_whitespace(char c);
}

// TOML Parser
class TomlParser {
public:
    TomlParser();
    ~TomlParser();
    
    // Parse TOML string
    std::shared_ptr<Table> parse(const std::string& input);
    
    // Get parse error if any
    std::string get_error() const { return error_message_; }
    bool has_error() const { return !error_message_.empty(); }

private:
    std::string error_message_;
    const char* current_;
    const char* end_;
    std::shared_ptr<Table> root_table_;
    std::shared_ptr<Table> current_table_;
    // Paths that were defined as array-of-tables [[x]], so [x.y] is allowed
    std::set<std::vector<std::string>> array_of_tables_paths_;

    // Path helpers for [table] and dotted keys
    std::vector<std::string> parse_dotted_key();
    std::shared_ptr<Table> get_or_create_table_at_path(const std::vector<std::string>& path);
    std::shared_ptr<Table> get_or_create_array_append_table(const std::vector<std::string>& path);
    void set_value_at_path(std::shared_ptr<Table> table, const std::vector<std::string>& path, const TomlValue& value);
    
    // Parse methods
    void parse_document();
    std::shared_ptr<Table> parse_table();
    void parse_key_value_pair(std::shared_ptr<Table> table);
    std::string parse_key();
    TomlValue parse_value();
    String parse_string();
    String parse_basic_string();
    String parse_literal_string();
    String parse_multiline_basic_string();
    String parse_multiline_literal_string();
    Integer parse_integer();
    Float parse_float();
    Boolean parse_boolean();
    DateTime parse_datetime();
    
    // Array parsing
    ArrayPtr parse_array();
    
    // Inline table: { key = value, ... }
    TablePtr parse_inline_table();
    
    // Date/time: only consumes input if parsing succeeds
    std::optional<TomlValue> try_parse_datetime();
    
    // Utility methods
    void skip_whitespace();
    void skip_whitespace_no_nl();
    void skip_comment();
    void expect_char(char c);
    bool peek_char(char c);
    char peek();
    char advance();
    bool eof();
    void set_error(const std::string& message);
    
    // String parsing helpers
    std::string parse_escape_sequence();
    std::string parse_unicode_escape(int num_hex_digits);
};

} // namespace fasttoml
