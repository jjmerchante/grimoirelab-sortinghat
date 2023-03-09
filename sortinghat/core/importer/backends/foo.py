from sortinghat.core.importer.backend import IdentitiesImporter


class FooImporter(IdentitiesImporter):

    NAME = 'foo'

    def __init__(self, url, token):
        super().__init__(url)
        self.token = token

    def run(self):
        pass
