cmake_minimum_required(VERSION 3.20)

# The fixture input is useful to exercise this gate without requiring a built
# ELF file. Exact Linux builds pass PLUGIN_FILE and NM_TOOL instead.
if(DEFINED NM_OUTPUT_FILE)
    if(NOT EXISTS "${NM_OUTPUT_FILE}")
        message(FATAL_ERROR "nm fixture does not exist: ${NM_OUTPUT_FILE}")
    endif()
    file(READ "${NM_OUTPUT_FILE}" nm_output)
else()
    if(NOT DEFINED PLUGIN_FILE OR NOT EXISTS "${PLUGIN_FILE}")
        message(FATAL_ERROR "PLUGIN_FILE must name the built Linux plugin or bridge")
    endif()
    if(NOT DEFINED NM_TOOL OR NM_TOOL STREQUAL "" OR NOT EXISTS "${NM_TOOL}")
        message(FATAL_ERROR "NM_TOOL must name nm or llvm-nm")
    endif()
    execute_process(
        COMMAND "${NM_TOOL}" --dynamic --undefined-only --format=posix "${PLUGIN_FILE}"
        RESULT_VARIABLE nm_result
        OUTPUT_VARIABLE nm_output
        ERROR_VARIABLE nm_error
    )
    if(NOT nm_result EQUAL 0)
        message(FATAL_ERROR
            "Unable to inspect ${PLUGIN_FILE} with ${NM_TOOL}: ${nm_error}")
    endif()
endif()

# Public endstone::* plugin symbols are supplied by libendstone_runtime when
# the plugin is loaded. Bedrock and endstone::core are private implementation
# ABIs: every strong reference must be resolved inside this exact plugin.
set(private_symbol_pattern
    "^_Z(NK?|TV|TI|TS)([0-9]+(Actor|BaseGameVersion|Block|BlockActor|BlockActorDataPacket|BlockPos|BlockSource|BlockType|ByteArrayTag|ByteTag|CompoundTag|Container|Dimension|DoubleTag|EndTag|FloatTag|GameMode|HashedString|Int64Tag|IntArrayTag|IntTag|Item|ItemDescriptor|ItemInstance|ItemRegistry|ItemRegistryManager|ItemStack|ItemStackBase|IVanillaMainBlockActorComponent|Level|LevelChunk|ListTag|Player|ServerPlayer|ShortTag|SignBlockActor|StringTag|Tag|WeakPtr|WeakRef)|N?8endstone4core)"
)

string(REPLACE "\r\n" "\n" nm_output "${nm_output}")
string(REPLACE "\n" ";" nm_lines "${nm_output}")
set(undefined_private_symbols)
foreach(line IN LISTS nm_lines)
    # POSIX nm output is: <symbol> <type> [value] [size]. Upper-case U is a
    # strong unresolved relocation; lower-case w/v denotes an optional weak
    # import and is intentionally ignored.
    if(line MATCHES "^([^ ]+) U([ ]|$)")
        set(symbol "${CMAKE_MATCH_1}")
        if(symbol MATCHES "${private_symbol_pattern}")
            list(APPEND undefined_private_symbols "${symbol}")
        endif()
    endif()
endforeach()

if(undefined_private_symbols)
    list(REMOVE_DUPLICATES undefined_private_symbols)
    list(SORT undefined_private_symbols)
    string(JOIN "\n  " formatted_symbols ${undefined_private_symbols})
    message(FATAL_ERROR
        "Plugin contains unresolved private Bedrock or Endstone-core ABI symbols:\n"
        "  ${formatted_symbols}\n"
        "Link the exact Endstone v0.11.6 Bedrock implementation; do not add guessed offsets or untyped no-op stubs."
    )
endif()

if(DEFINED PLUGIN_FILE)
    message(STATUS
        "Verified that ${PLUGIN_FILE} has no unresolved private Bedrock ABI symbols")
endif()
