"""What is known of the files of the images (#248) — what their metadata say (read with ExifTool: the camera, the capture date, any field), whether
they decode, their hashes —, each found out once while the file is the same and remembered: in memory, and on disk so that a restart does not read
them again (#140). The validation, the preprocessing, the seal and the reports ask it through its contract (FileInfoService)."""
