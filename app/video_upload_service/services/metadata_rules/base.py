class MetadataRule:

    version = "v1"

    def validate(self, metadata: dict):
        raise NotImplementedError
