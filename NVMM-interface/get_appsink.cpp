#include <gstnvdsmeta.h>

GstSample *sample = gst_app_sink_pull_sample(appsink);
GstBuffer *buffer = gst_sample_get_buffer(sample);

GstMemory *mem = gst_buffer_peek_memory(buffer, 0);
if (!mem) {
    // handle error
}

// Ensure this is NVMM memory
if (!gst_is_nv_memory(mem)) {
    // You lost zero-copy somewhere
}

// Extract NvBufSurface
NvBufSurface *surface = (NvBufSurface *) gst_nv_buffer_get_nvbuf_surface(buffer);