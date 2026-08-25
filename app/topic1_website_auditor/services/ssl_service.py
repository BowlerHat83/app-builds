import socket
import ssl
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel


class SSLCertificateInfo(BaseModel):
    domain: str
    issuer: str
    subject: str
    valid_from: str
    valid_until: str
    days_remaining: int
    is_expired: bool
    is_expiring_soon: bool  # Flagged if < 30 days remaining
    sans: List[str]
    serial_number: str
    signature_algorithm: str
    error: Optional[str] = None


def check_ssl_certificate(domain: str, port: int = 443, warning_threshold_days: int = 30) -> SSLCertificateInfo:
    """Connects to a domain over SSL/TLS and extracts certificate expiration and metadata."""
    # Clean protocol prefix if present (e.g., https://example.com -> example.com)
    clean_domain = domain.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]

    context = ssl.create_default_context()

    try:
        with socket.create_connection((clean_domain, port), timeout=10.0) as sock:
            with context.wrap_socket(sock, server_hostname=clean_domain) as ssock:
                cert = ssock.getpeercert()

                # Extract Validity Dates
                # Format: 'Jan 15 12:00:00 2026 GMT'
                date_fmt = "%b %d %H:%M:%S %Y %Z"
                not_before = datetime.strptime(cert["notBefore"], date_fmt).replace(tzinfo=timezone.utc)
                not_after = datetime.strptime(cert["notAfter"], date_fmt).replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)

                # Calculate days remaining
                days_remaining = (not_after - now).days
                is_expired = days_remaining <= 0
                is_expiring_soon = days_remaining < warning_threshold_days

                # Extract Issuer Organization
                issuer_dict = dict(x[0] for x in cert.get("issuer", ()))
                issuer = issuer_dict.get("organizationName") or issuer_dict.get("commonName") or "Unknown Issuer"

                # Extract Subject
                subject_dict = dict(x[0] for x in cert.get("subject", ()))
                subject = subject_dict.get("commonName") or clean_domain

                # Extract SANs (Subject Alternative Names)
                sans = [item[1] for item in cert.get("subjectAltName", ()) if item[0] == "DNS"]

                return SSLCertificateInfo(
                    domain=clean_domain,
                    issuer=issuer,
                    subject=subject,
                    valid_from=not_before.isoformat(),
                    valid_until=not_after.isoformat(),
                    days_remaining=days_remaining,
                    is_expired=is_expired,
                    is_expiring_soon=is_expiring_soon,
                    sans=sans,
                    serial_number=str(cert.get("serialNumber", "")),
                    signature_algorithm=cert.get("signatureAlgorithm", "sha256WithRSAEncryption"),
                )

    except Exception as e:
        return SSLCertificateInfo(
            domain=clean_domain,
            issuer="Unknown",
            subject="Unknown",
            valid_from="",
            valid_until="",
            days_remaining=0,
            is_expired=True,
            is_expiring_soon=True,
            sans=[],
            serial_number="",
            signature_algorithm="",
            error=str(e),
        )