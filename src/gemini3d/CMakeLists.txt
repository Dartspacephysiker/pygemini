cmake_minimum_required(VERSION 3.15)

include(cmake/policy.cmake)
include(cmake/compiler_find.cmake)
find_c_fortran()

project(MSIS LANGUAGES Fortran)

include(CTest)
if(NOT DEFINED ${PROJECT_NAME}_BUILD_TESTING)
  set(${PROJECT_NAME}_BUILD_TESTING ${BUILD_TESTING})
endif()

option(msis20 "build MSIS 2.0")

if(msis20)
  include(cmake/libraries.cmake)
endif()

if(NOT DEFINED gemini_root)
  if(DEFINED ENV{GEMINI_ROOT})
    set(gemini_root $ENV{GEMINI_ROOT})
  else()
    set(gemini_root ${CMAKE_CURRENT_SOURCE_DIR}/gemini-fortran)
  endif()
endif()

# It's necessary to resolve the path on Windows in particular
# otherwise add_subdirectory() may fail to find the path
get_filename_component(gemini_root ${gemini_root} ABSOLUTE)

# --- build msis_setup executable
add_subdirectory(${gemini_root}/src/vendor/msis00 ${PROJECT_BINARY_DIR}/msis)

set_target_properties(msis_setup PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR})

file(TOUCH ${PROJECT_BINARY_DIR}/__init__.py)
