def _merge_native_data(base_data, base_meta, native_data, meta_patch):
    merged = dict(base_data); merged.update(native_data)
    meta = dict(base_meta); meta.update(meta_patch)
    return merged, meta
