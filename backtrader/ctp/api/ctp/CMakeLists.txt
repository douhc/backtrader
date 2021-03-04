cmake_minimum_required(VERSION 3.10)

set(CMAKE_VERBOSE_MAKEFILE ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

project(vnctp VERSION 0.0.1 LANGUAGES CXX)

set(LIBRARY_OUTPUT_PATH ${PROJECT_SOURCE_DIR})

add_library(
  vnctp SHARED
  vnctp/vnctpmd/vnctpmd.cpp 
  vnctp/vnctptd/vnctptd.cpp 
  )

target_include_directories(
  vnctp
  PRIVATE ${PROJECT_SOURCE_DIR}/include
  PRIVATE ${PROJECT_SOURCE_DIR}/vnctp
  )

set_target_properties(
  vnctp PROPERTIES
  COMPILE_DEFINITIONS ""
  COMPILE_FLAGS "-Wall"
  LINK_FLAGS ""
  )

target_compile_features(
  vnctp 
  PRIVATE cxx_std_11
  )

target_link_libraries(
  vnctp
  PUBLIC -L${PROJECT_SOURCE_DIR}
  PRIVATE thostmduserapi
  PRIVATE thosttraderapi
)
