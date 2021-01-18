if(CMAKE_VERSION VERSION_LESS 3.19)
  message(FATAL_ERROR "CMake >= 3.19 required for MSIS 2.0")
endif()

file(READ ${CMAKE_CURRENT_SOURCE_DIR}/libraries.json _libj)

string(JSON gemini3d_url GET ${_libj} gemini3d url)
string(JSON gemini3d_tag GET ${_libj} gemini3d tag)

string(JSON msis2_url GET ${_libj} msis2 url)
string(JSON msis2_sha1 GET ${_libj} msis2 sha1)
