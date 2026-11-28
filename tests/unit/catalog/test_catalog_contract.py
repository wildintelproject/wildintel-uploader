"""#248: the contract of the catalog is its parts — whoever needs only some of it asks for that part."""
from wildintel_uploader.modules.catalog.domain import ports

PARTS = (ports.CatalogPeople, ports.CatalogProjects, ports.CatalogLocations, ports.CatalogEquipment, ports.CatalogRoles, ports.CatalogHistory,
         ports.CatalogCheckpoints, ports.CatalogFieldwork)


def _operations(contract) -> list[str]:
    return [name for name, value in vars(contract).items() if not name.startswith("_") and callable(value)]


def test_the_contract_of_the_catalog_is_its_parts_each_operation_in_one_of_them():
    operations = [name for part in PARTS for name in _operations(part)]
    assert len(operations) == len(set(operations)) == 31
    assert set(ports.CatalogService.__bases__) >= set(PARTS) and not _operations(ports.CatalogService)


def test_the_use_cases_do_every_operation_of_the_catalog():
    from wildintel_uploader.modules.catalog.application.use_cases import CatalogUseCases
    assert {name for part in PARTS for name in _operations(part)} <= set(dir(CatalogUseCases))


def test_the_container_gives_each_part_of_the_catalog_as_the_same_catalog():
    from wildintel_uploader.entrypoints import wiring

    container = wiring.make_app_container()
    with container() as request:
        whole = request.get(ports.CatalogService)
        assert all(request.get(part) is whole for part in PARTS)
    container.close()
