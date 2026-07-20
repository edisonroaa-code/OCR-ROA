cmake_minimum_required(VERSION 3.16)
project(idrs_wrapper LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(idrs_wrapper main.cpp)

target_compile_definitions(idrs_wrapper PRIVATE UNICODE _UNICODE)
