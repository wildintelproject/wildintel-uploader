"""The preprocessing (#248, #246): the images of a deployment as they are imported into their collection — the date of each in UTC, its new name,
resized, its hashes, the XMP of its authorship and license —, each step a class in infrastructure/steps; prepared in the .staging folder of the
collection and, once saved, moved to its place and sealed. What wildintel-tools' prepare_collections_for_trapper did, and a bit more."""
