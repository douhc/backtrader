cmake_minimum_required(VERSION 3.10)

set(CMAKE_VERBOSE_MAKEFILE ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

project(vnctp VERSION 0.0.1 LANGUAGES CXX)

set(LIBRARY_OUTPUT_PATH ${PROJECT_SOURCE_DIR})

############# vnctpmd ##############
add_library(
  vnctpmd SHARED
  vnctp/vnctpmd/vnctpmd.cpp 
  )

target_include_directories(
  vnctpmd
  PRIVATE ${PROJECT_SOURCE_DIR}/include
  PRIVATE ${PROJECT_SOURCE_DIR}/vnctp
  PRIVATE /usr/include/python3.8
  )

set_target_properties(
  vnctpmd PROPERTIES
  COMPILE_DEFINITIONS ""
  COMPILE_FLAGS "-Wall"
  LINK_FLAGS ""
  )

target_compile_features(
  vnctpmd 
  PRIVATE cxx_std_11
  )

target_link_libraries(
  vnctpmd
  PUBLIC -L${PROJECT_SOURCE_DIR}
  PRIVATE thostmduserapi_se
)

############# vnctptd ##############
add_library(
  vnctptd SHARED
  vnctp/vnctptd/vnctptd.cpp 
  )

target_include_directories(
  vnctptd
  PRIVATE ${PROJECT_SOURCE_DIR}/include
  PRIVATE ${PROJECT_SOURCE_DIR}/vnctp
  PRIVATE /usr/include/python3.8
  )

set_target_properties(
  vnctpmd PROPERTIES
  COMPILE_DEFINITIONS ""
  COMPILE_FLAGS "-Wall"
  LINK_FLAGS ""
  )

target_compile_features(
  vnctptd 
  PRIVATE cxx_std_11
  )

target_link_libraries(
  vnctptd
  PUBLIC -L${PROJECT_SOURCE_DIR}
  PRIVATE thosttraderapi_se
)
