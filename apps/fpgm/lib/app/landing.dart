import 'dart:async';
import 'package:flutter/material.dart';
// Plugin imports
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';

class LandingPage extends StatefulWidget {
  const LandingPage({super.key});

  @override
  State<LandingPage> createState() => _LandingPageState();
}

class _LandingPageState extends State<LandingPage> {
  final MapController _mapController = MapController();

  StreamSubscription<Position>? _positionSubscription;

  LatLng? _userLocation;
  bool _mapReady = false;
  bool _hasCentered = false;
  String? _locationError;

  @override
  void initState() {
    super.initState();
    _startLocationTracking();
  }

  Future<void> _startLocationTracking() async {
    try {
      var permission = await Geolocator.checkPermission();

      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      if (!mounted) return;

      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        setState(() {
          _locationError = 'Location permission was not granted.';
        });
        return;
      }

      const settings = LocationSettings(
        accuracy: LocationAccuracy.best,
        distanceFilter: 10,
      );

      _positionSubscription =
          Geolocator.getPositionStream(
            locationSettings: settings,
          ).listen(
                (position) {
              if (!mounted) return;

              final location = LatLng(
                position.latitude,
                position.longitude,
              );

              setState(() {
                _userLocation = location;
                _locationError = null;
              });

              if (!_hasCentered && _mapReady) {
                _hasCentered = true;
                _mapController.move(location, 16);
              }
            },
            onError: (Object error) {
              if (!mounted) return;

              setState(() {
                _locationError = 'Unable to receive location updates.';
              });
            },
          );
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _locationError = 'Could not access your location.';
      });
    }
  }

  void _centerOnUser() {
    final location = _userLocation;
    if (location == null || !_mapReady) return;

    _mapController.move(location, 16);
  }

  @override
  void dispose() {
    _positionSubscription?.cancel();
    _mapController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final location = _userLocation;

    return Scaffold(
      body: Stack(
        children: [
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCenter: const LatLng(0, 0),
              initialZoom: 2,
              minZoom: 2,
              maxZoom: 19,
              onMapReady: () {
                _mapReady = true;

                if (!_hasCentered && _userLocation != null) {
                  _hasCentered = true;
                  _mapController.move(_userLocation!, 16);
                }
              },
            ),
            children: [
              TileLayer(
                urlTemplate:
                'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.example.fpgm',
              ),
              if (location != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      point: location,
                      width: 64,
                      height: 64,
                      child: Container(
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.blue.withValues(alpha: 0.16),
                        ),
                        child: Container(
                          width: 24,
                          height: 24,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: Colors.blue,
                            border: Border.all(
                              color: Colors.white,
                              width: 4,
                            ),
                            boxShadow: const [
                              BoxShadow(
                                color: Colors.black26,
                                blurRadius: 8,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              const RichAttributionWidget(
                attributions: [
                  TextSourceAttribution('OpenStreetMap contributors'),
                ],
              ),
            ],
          ),

          Positioned(
            right: 16,
            bottom: 32,
            child: FloatingActionButton(
              onPressed: _centerOnUser,
              tooltip: 'Center on my location',
              child: const Icon(Icons.my_location),
            ),
          ),

          if (location == null)
            Positioned(
              top: 24,
              left: 16,
              right: 16,
              child: SafeArea(
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(
                      _locationError ??
                          'Finding your location… Please allow location access.',
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
