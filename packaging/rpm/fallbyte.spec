Name:           fallbyte
Version:        1.0.0
Release:        1%{?dist}
Summary:        Local-first media optimization tool

License:        MIT
URL:            https://github.com/brunothinker/fallbyte
BuildArch:      x86_64

# Disable automatic dependency generator only for PyInstaller internal libraries
%global __requires_exclude ^lib.*\\.so.*$
AutoReq:        yes
AutoProv:       yes

Requires:       mpv-libs, gtk3, gstreamer1, gstreamer1-plugins-base

%description
Local-first media optimization tool for images and videos built with Flet.

%prep

%build

%install
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_libdir}/%{name}/_internal
mkdir -p %{buildroot}%{_datadir}/applications
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/256x256/apps

# Copy compiled PyInstaller build artifacts
cp -r %{_sourcedir}/FallByte/* %{buildroot}%{_libdir}/%{name}/
cp %{_sourcedir}/fallbyte_icon.png %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/%{name}.png

# Symlink binary executable into system PATH
ln -s %{_libdir}/%{name}/FallByte %{buildroot}%{_bindir}/%{name}

# Compatibility symlink targeting system shared library path in /usr/lib64
ln -sf %{_libdir}/libmpv.so.2 %{buildroot}%{_libdir}/%{name}/_internal/libmpv.so.1

# Generate XDG desktop launcher entry
cat <<EOF > %{buildroot}%{_datadir}/applications/%{name}.desktop
[Desktop Entry]
Name=FallByte
Comment=Local-first media optimization tool
Exec=%{_bindir}/%{name}
Icon=%{name}
Terminal=false
Type=Application
Categories=AudioVideo;Video;Graphics;
Keywords=media;compress;video;image;optimization;
EOF

%files
%{_bindir}/%{name}
%{_libdir}/%{name}/
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/256x256/apps/%{name}.png

%changelog
* Tue Sep 15 2026 Bruno Henrique <brunothinker@github.com> - 1.0.0-1
- Fix libmpv symlink resolution targeting system library path.