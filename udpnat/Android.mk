LOCAL_PATH:= $(call my-dir)

include $(CLEAR_VARS)

LOCAL_MODULE := udpnat_server
LOCAL_MODULE_TAGS := optional

LOCAL_SRC_FILES := udpnat.c

include $(BUILD_HOST_EXECUTABLE)

include $(CLEAR_VARS)

LOCAL_MODULE := udpnat_client
LOCAL_MODULE_TAGS := optional

LOCAL_SRC_FILES := udpnat.c
LOCAL_STATIC_LIBRARIES := libc
LOCAL_FORCE_STATIC_EXECUTABLE := true

include $(BUILD_EXECUTABLE)
