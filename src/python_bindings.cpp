#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/chrono.h>
#include "fasttoml/toml_parser.hpp"
#include <memory>
#include <string>

namespace py = pybind11;
using namespace fasttoml;

// Forward declaration
py::object toml_value_to_python(const TomlValue& value);

// Convert C++ Table to Python dict
py::dict table_to_dict(const Table& table) {
    py::dict result;
    
    for (const auto& [key, value] : table.values) {
        result[py::str(key)] = toml_value_to_python(value);
    }
    
    return result;
}

// Convert C++ TomlValue to Python object
py::object toml_value_to_python(const TomlValue& value) {
    return std::visit([](auto&& arg) -> py::object {
        using T = std::decay_t<decltype(arg)>;
        
        if constexpr (std::is_same_v<T, Integer>) {
            return py::cast(arg);
        } else if constexpr (std::is_same_v<T, Float>) {
            return py::cast(arg);
        } else if constexpr (std::is_same_v<T, Boolean>) {
            return py::cast(arg);
        } else if constexpr (std::is_same_v<T, String>) {
            return py::cast(arg);
        } else if constexpr (std::is_same_v<T, DateTime>) {
            // Return datetime in UTC (Z)
            namespace sc = std::chrono;
            auto epoch = sc::system_clock::from_time_t(0);
            double secs = sc::duration_cast<sc::duration<double>>(arg - epoch).count();
            py::module_ datetime = py::module_::import("datetime");
            py::object utc = datetime.attr("timezone").attr("utc");
            return datetime.attr("datetime").attr("fromtimestamp")(py::cast(secs), utc);
        } else if constexpr (std::is_same_v<T, DateTimeOffset>) {
            // Return datetime with original offset for correct RFC 3339 output
            namespace sc = std::chrono;
            auto epoch = sc::system_clock::from_time_t(0);
            double secs = sc::duration_cast<sc::duration<double>>(arg.utc - epoch).count();
            py::module_ datetime = py::module_::import("datetime");
            py::object tz = datetime.attr("timezone")(datetime.attr("timedelta")(py::arg("minutes") = arg.offset_minutes));
            return datetime.attr("datetime").attr("fromtimestamp")(py::cast(secs), tz);
        } else if constexpr (std::is_same_v<T, TablePtr>) {
            return table_to_dict(*arg);
        } else if constexpr (std::is_same_v<T, ArrayPtr>) {
            py::list result;
            for (const auto& elem : arg->elements) {
                result.append(toml_value_to_python(elem));
            }
            return result;
        }
    }, value);
}

// Python loads function
py::dict loads(const std::string& toml_string) {
    TomlParser parser;
    auto table = parser.parse(toml_string);
    
    if (!table) {
        if (parser.has_error()) {
            throw std::runtime_error("TOML parse error: " + parser.get_error());
        } else {
            throw std::runtime_error("TOML parse error: unknown error");
        }
    }
    
    return table_to_dict(*table);
}

PYBIND11_MODULE(_native, m) {
    m.doc() = "Fast TOML parser for Python with SIMD optimizations";
    
    // Main API
    m.def("loads", &loads, R"pbdoc(
        Parse a TOML string and return a dictionary.
        
        Args:
            toml_string: The TOML string to parse
            
        Returns:
            dict: Parsed TOML data as a Python dictionary
            
        Raises:
            RuntimeError: If parsing fails
    )pbdoc", py::arg("toml_string"));
    
    // Version info
    m.attr("__version__") = "0.1.0";
}
