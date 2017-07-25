from ww import f

__all__ = ['generate_stubs']


def generate_stubs():
    import re
    from collections import defaultdict

    try:
        import autopep8
        import requests
        from bs4 import BeautifulSoup
        from stringcase import camelcase
    except ImportError:
        raise RuntimeError('Please `pip install reqs/infusionsoft_stubs.txt` '
                           'before generating stubs')

    INFUSIONSOFT_DOCS_URL = 'https://developer.infusionsoft.com/docs/xml-rpc/'
    response = requests.get(INFUSIONSOFT_DOCS_URL)
    assert response.status_code == 200
    doc = BeautifulSoup(response.content, 'html.parser')

    el_calls = doc.find_all(class_='method',
                            id=re.compile('^(?!introduction)'))
    services = defaultdict(dict)
    for el_call in el_calls:
        if not el_call.find(class_='lang-xml'):
            # These are introduction sections
            continue

        # Parse parameters
        params = []
        for el_arg in el_call.find_all(class_='argument'):
            argname = el_arg.find(class_='col-sm-4').find('b').text.rstrip(':')
            # Sometimes these are human descriptions, not keywords... for shame
            argname = camelcase(argname.replace(' ', ''))

            full_desc = el_arg.find(class_='col-sm-8').text.strip()
            argdesc = full_desc.split('\n', 1)[0]
            type = re.split(r'\s+', argdesc, 1)[0]

            # Infusionsoft mislabels all params named "data" as "array",
            # because it dubs them "associative arrays". Arrays in XML-RPC are
            # lists of data. Associatve arrays are structs. Infusionsoft even
            # uses "struct" correctly elsewhere. Blech. </rant>
            if argname == 'data':
                type = 'struct'

            params.append((argname, type))

        # Parse return value from example response value
        rtype = 'None'
        el_resp_xml = el_call.find(class_='method-response lang-xml')
        if el_resp_xml:
            resp_xml = el_resp_xml.text
            el_resp = BeautifulSoup(resp_xml, 'html.parser')
            el_value = el_resp.find('value')
            if el_value:
                el_val_children = el_value.findChildren()
                if el_val_children:
                    # An explicit <array>, <int>, <string>, etc under <value>
                    el_rtype =el_val_children [0]
                    rtype = el_rtype.name
                else:
                    # Just text under <value> implies <string>
                    rtype = 'string'

        # Parse method title and description
        el_title = el_call.find('h3')
        title = el_title.find(text=True).strip()

        el_meth_desc = el_call.find(class_='method-description')
        el_desc_paras = el_meth_desc.findAll('p', recursive=False)
        desc = '\n\n'.join(el_p.text.strip() for el_p in el_desc_paras)

        # Parse method name
        el_definition = el_call.find(class_='method-declaration lang-xml')
        if el_definition:
            # Most calls have a "Definition" section listing only the name
            name = el_definition.text.strip()
        else:
            # But some do not, and we must parse the example request XML
            req_xml = el_call.find(class_='method-request lang-xml').text
            el_req = BeautifulSoup(req_xml, 'html.parser')
            name = el_req.find('methodname').text

        service, method = name.split('.', 1)
        services[service][method] = (params, rtype, title, desc)

    lines = [
        'from typing import List, Dict',
        'from datetime import datetime',
        '',
        '',
    ]

    TYPE_MAP = {
        'i4': 'int',
        'integer': 'int',
        'double': 'float',
        'dateTime': 'datetime',
        'dateTime.iso8601': 'datetime',
        'array': 'List',
        'string': 'str',
        'struct': 'Dict[str, any]',
        'boolean': 'bool',
    }
    services = sorted(services.items())
    for service, methods in services:
        lines.append(f('class {service}:'))
        methods = sorted(methods.items())
        for name, (params, rtype, title, desc) in methods:
            # apiKey is always first param, which is handled automatically by
            # DefaultArgServerProxy, so we ignore it here.
            params = params[1:]
            params = [f('{n}: {TYPE_MAP.get(t, t)}') for n, t in params]

            rtype = TYPE_MAP.get(rtype, rtype)

            indent = ' ' * 8
            docstring_parts = [title + '\n' if title else None]
            docstring_parts += [(indent + line).rstrip()
                                for line in desc.split('\n')]
            docstring_contents = '\n'.join(docstring_parts).strip()

            indent = ' ' * 4
            meth_lines = [
                f('@staticmethod'),
                f('def {name}({", ".join(params)}) -> {rtype}:'),
                f('    """{docstring_contents}'),
                f('    """'),
                f('    pass'),
                f(''),
            ]
            lines += [indent + line for line in meth_lines]
        lines.append('')

    # Format according to PEP-8 (doesn't work very well)
    source = '\n'.join(lines)
    source = autopep8.fix_code(source, {'max_line_length': 79})

    return source
