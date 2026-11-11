"""Public domains and explicitly configured loopback endpoints, without URL data."""
import ipaddress
import re
from urllib.parse import urlsplit


def is_local_site(value):
    return isinstance(value,str) and bool(re.fullmatch(r'127\.0\.0\.1:[1-9][0-9]{0,4}',value)) and int(value.rsplit(':',1)[1])<=65535


def domain(value):
    error='Enter a website domain, for example youtube.com.'
    if not isinstance(value,str) or len(value)>2048:raise ValueError(error)
    raw=value.strip().lower()
    if raw.startswith('*.'):raw=raw[2:]
    explicit='://' in raw
    try:
        parsed=urlsplit(raw if explicit else 'https://'+raw)
        if parsed.scheme not in ('http','https') or parsed.username or parsed.password:raise ValueError(error)
        host=(parsed.hostname or '').rstrip('.').encode('idna').decode('ascii')
        port=parsed.port
        if port is not None and not 1<=port<=65535:raise ValueError(error)
    except (ValueError,UnicodeError):raise ValueError(error) from None
    if host in ('localhost','127.0.0.1','::1'):
        port=port or (443 if explicit and parsed.scheme=='https' else 80)
        return f'127.0.0.1:{port}'
    try:ipaddress.ip_address(host)
    except ValueError:pass
    else:raise ValueError(error)
    if (len(host)>253 or '.' not in host or host.endswith(('.local','.localhost','.internal','.test','.invalid'))
            or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',part) for part in host.split('.'))):raise ValueError(error)
    return host


def configured_local_sites(settings,focus,bridge_port=47853):
    members=[m['value'] for rule in settings.wellbeing_rules for m in rule['members'] if m['kind']=='site']
    return sorted({value for value in [*members,*focus.block_sites] if is_local_site(value) and value!=f'127.0.0.1:{bridge_port}'})


def compatible_local_policy(policy,supported):
    """Old workers must reach their automatic reload without invalid DNR domains."""
    if supported or policy is None:return policy
    result=dict(policy,local_sites=[])
    for field in ('block','allow'):
        if field in result:result[field]=[host for host in result[field] if not is_local_site(host)]
    for field in ('restrictions','choice_rules'):
        if field not in result:continue
        values=[]
        for entry in result[field]:
            domains=[host for host in entry.get('domains',()) if not is_local_site(host)]
            if entry.get('all') or domains:values.append(dict(entry,domains=domains))
        result[field]=values
    return result
