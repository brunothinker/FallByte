Name:           fallbyte
Version:        %{?_version}%{!?_version:dev}
Release:        1%{?dist}
Summary:        Local-first media optimization and conversion suite

License:        GPL-3.0-or-later
URL:            https://github.com/brunothinker/FallByte
BuildArch:      x86_64

# Disable automatic dependency generator only for PyInstaller internal libraries
%global __requires_exclude ^lib.*\\.so.*$
AutoReq:        yes
AutoProv:       yes

Requires:       mpv-libs, gtk3, gstreamer1, gstreamer1-plugins-base, libheif, openssl-libs

%description
FallByte is a fast, local-first desktop utility for compressing, optimizing,
and converting media files completely offline.

Designed with privacy, batch processing, and workflow efficiency in mind, it
helps reduce file sizes and standardize formats directly on your machine
without relying on cloud services.

%prep

%build

%install
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_libdir}/%{name}/_internal
mkdir -p %{buildroot}%{_datadir}/applications
mkdir -p %{buildroot}%{_datadir}/metainfo
mkdir -p %{buildroot}%{_docdir}/%{name}

# Copy compiled PyInstaller build artifacts
cp -r %{_sourcedir}/FallByte/* %{buildroot}%{_libdir}/%{name}/

# Remove Conda-bundled OpenSSL so Fedora's system OpenSSL is used cleanly
rm -f %{buildroot}%{_libdir}/%{name}/_internal/libcrypto.so*
rm -f %{buildroot}%{_libdir}/%{name}/_internal/libssl.so*

# Install multi-size application icons
for SIZE in 48 128 256 512; do
    mkdir -p %{buildroot}%{_datadir}/icons/hicolor/${SIZE}x${SIZE}/apps
    cp %{_sourcedir}/icons/${SIZE}x${SIZE}/%{name}.png %{buildroot}%{_datadir}/icons/hicolor/${SIZE}x${SIZE}/apps/%{name}.png
done

# Copy AppStream metadata, license, and third-party notices if present
if [ -f "%{_sourcedir}/fallbyte.metainfo.xml" ]; then
    cp "%{_sourcedir}/fallbyte.metainfo.xml" %{buildroot}%{_datadir}/metainfo/
fi

if [ -f "%{_sourcedir}/LICENSE" ]; then
    cp "%{_sourcedir}/LICENSE" %{buildroot}%{_docdir}/%{name}/
fi

if [ -f "%{_sourcedir}/THIRD_PARTY_NOTICES.md" ]; then
    cp "%{_sourcedir}/THIRD_PARTY_NOTICES.md" %{buildroot}%{_docdir}/%{name}/
fi

# Symlink binary executable into system PATH
ln -s %{_libdir}/%{name}/FallByte %{buildroot}%{_bindir}/%{name}

# Compatibility symlink targeting system shared library path in /usr/lib64
ln -sf %{_libdir}/libmpv.so.2 %{buildroot}%{_libdir}/%{name}/_internal/libmpv.so.1

# Generate XDG desktop launcher entry
cat <<EOF > %{buildroot}%{_datadir}/applications/%{name}.desktop
[Desktop Entry]
Name=FallByte
Comment=Local-first media optimization and conversion suite
Exec=%{_bindir}/%{name}
Icon=%{name}
Terminal=false
Type=Application
Categories=AudioVideo;
Keywords=media;compress;convert;optimization;offline;
EOF

%post
/sbin/ldconfig || :
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t %{_datadir}/icons/hicolor >/dev/null 2>&1 || :
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q %{_datadir}/applications >/dev/null 2>&1 || :
fi

%postun
/sbin/ldconfig || :
if [ $1 -eq 0 ]; then
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t %{_datadir}/icons/hicolor >/dev/null 2>&1 || :
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q %{_datadir}/applications >/dev/null 2>&1 || :
    fi
fi

%files
%{_bindir}/%{name}
%{_libdir}/%{name}/
%{_datadir}/applications/%{name}.desktop
%{_datadir}/metainfo/fallbyte.metainfo.xml
%{_datadir}/icons/hicolor/*/apps/%{name}.png
%license %{_docdir}/%{name}/LICENSE
%doc %{_docdir}/%{name}/THIRD_PARTY_NOTICES.md

%changelog
* Wed Nov 18 2026 Bruno Henrique <brunothinker@github.com> - 2.0.0-1
- Add multi-size icons, AppStream metainfo, license docs, cache hooks, and dynamic version macro.