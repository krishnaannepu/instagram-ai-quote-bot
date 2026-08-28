from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


class BusinessKnowledgeAdapterError(RuntimeError):
    pass


class BusinessKnowledgeAdapterV3:
    """
    Read-only adapter over the existing production business_knowledge_service.

    V3 does not duplicate pricing/package/business policy data.
    Google Sheets remains the business-editable source of truth.
    """

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        service_module=None,
    ):
        self.project_root = (
            Path(project_root).resolve()
            if project_root
            else Path(__file__).resolve().parent.parent
        )
        self._service_module = service_module

    def _service(self):
        if self._service_module is not None:
            return self._service_module

        project_root_text = str(self.project_root)

        if project_root_text not in sys.path:
            sys.path.insert(
                0,
                project_root_text,
            )

        try:
            import business_knowledge_service
        except Exception as error:
            raise BusinessKnowledgeAdapterError(
                "Could not import the existing "
                "business_knowledge_service.py from the project root."
            ) from error

        self._service_module = business_knowledge_service
        return self._service_module

    def get_all(
        self,
        *,
        force_refresh: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        service = self._service()

        try:
            knowledge = service.get_business_knowledge(
                force_refresh=force_refresh
            )
        except Exception as error:
            raise BusinessKnowledgeAdapterError(
                "Could not load approved business knowledge."
            ) from error

        required_keys = {
            "pricing",
            "packages",
            "business_info",
            "faqs",
        }

        missing = (
            required_keys
            - set(
                knowledge.keys()
            )
        )

        if missing:
            raise BusinessKnowledgeAdapterError(
                f"Business knowledge is missing sections: "
                f"{sorted(missing)}"
            )

        return knowledge

    def get_pricing_rows(
        self,
    ) -> list[dict[str, Any]]:
        return list(
            self.get_all()["pricing"]
        )

    def get_package_rows(
        self,
    ) -> list[dict[str, Any]]:
        return list(
            self.get_all()["packages"]
        )

    def get_business_info_rows(
        self,
    ) -> list[dict[str, Any]]:
        return list(
            self.get_all()["business_info"]
        )

    def get_faq_rows(
        self,
    ) -> list[dict[str, Any]]:
        return list(
            self.get_all()["faqs"]
        )

    def get_pricing(
        self,
        service_name: str,
        package_name: str,
    ) -> dict[str, Any] | None:
        normalized_service = (
            str(
                service_name
                or ""
            )
            .strip()
            .lower()
        )
        normalized_package = (
            str(
                package_name
                or ""
            )
            .strip()
            .lower()
        )

        for row in self.get_pricing_rows():
            if (
                str(
                    row.get(
                        "service",
                        "",
                    )
                )
                .strip()
                .lower()
                == normalized_service
                and
                str(
                    row.get(
                        "package",
                        "",
                    )
                )
                .strip()
                .lower()
                == normalized_package
            ):
                return row

        return None

    def get_package(
        self,
        service_name: str,
        package_name: str,
    ) -> dict[str, Any] | None:
        normalized_service = (
            str(
                service_name
                or ""
            )
            .strip()
            .lower()
        )
        normalized_package = (
            str(
                package_name
                or ""
            )
            .strip()
            .lower()
        )

        for row in self.get_package_rows():
            if (
                str(
                    row.get(
                        "service",
                        "",
                    )
                )
                .strip()
                .lower()
                == normalized_service
                and
                str(
                    row.get(
                        "package",
                        "",
                    )
                )
                .strip()
                .lower()
                == normalized_package
            ):
                return row

        return None

    def get_catalogue(
        self,
    ) -> dict[str, Any]:
        knowledge = self.get_all()

        services: list[str] = []
        packages_by_service: dict[str, list[str]] = {}

        for row in (
            knowledge["pricing"]
            + knowledge["packages"]
        ):
            service_name = str(
                row.get(
                    "service",
                    "",
                )
            ).strip()

            package_name = str(
                row.get(
                    "package",
                    "",
                )
            ).strip()

            if (
                service_name
                and service_name
                not in services
            ):
                services.append(
                    service_name
                )

            if (
                service_name
                and package_name
            ):
                packages = (
                    packages_by_service
                    .setdefault(
                        service_name,
                        [],
                    )
                )

                if (
                    package_name
                    not in packages
                ):
                    packages.append(
                        package_name
                    )

        return {
            "supported_services":
                services,
            "packages_by_service":
                packages_by_service,
        }
